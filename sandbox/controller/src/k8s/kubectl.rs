use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;

use async_trait::async_trait;
use tokio::process::Command;
use tokio::time::timeout;

use crate::domain::errors::DomainError;
use crate::domain::models::ResourceRef;
use crate::k8s::{
    ApplyResult, ClusterBackend, DestroyOutcome, HttpHealthResult, NamespaceSpec, ObservedContainerStatus,
    ObservedEvent, ObservedPod, RolloutStatus, WorkloadObservation,
};
use crate::k8s::types::default_labels;

pub struct KubectlCluster {
    kubeconfig: Option<PathBuf>,
    context: Option<String>,
}

impl KubectlCluster {
    pub fn from_env() -> anyhow::Result<Self> {
        Ok(Self {
            kubeconfig: std::env::var_os("KUBECONFIG").map(PathBuf::from),
            context: std::env::var("RAPHAEL_KUBE_CONTEXT").ok(),
        })
    }

    fn base_cmd(&self) -> Command {
        let mut cmd = Command::new("kubectl");
        if let Some(cfg) = &self.kubeconfig {
            cmd.arg("--kubeconfig").arg(cfg);
        }
        if let Some(ctx) = &self.context {
            cmd.arg("--context").arg(ctx);
        }
        cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
        cmd
    }

    async fn run(&self, args: &[&str], max: Duration) -> Result<(i32, String, String), DomainError> {
        let mut cmd = self.base_cmd();
        cmd.args(args);
        let fut = cmd.output();
        let output = timeout(max, fut)
            .await
            .map_err(|_| DomainError::Timeout(format!("kubectl {} timed out", args.join(" "))))?
            .map_err(|e| DomainError::ClusterUnavailable(e.to_string()))?;
        let code = output.status.code().unwrap_or(1);
        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        Ok((code, stdout, stderr))
    }
}

#[async_trait]
impl ClusterBackend for KubectlCluster {
    fn name(&self) -> &'static str {
        "kubectl"
    }

    async fn create_isolated_namespace(&self, spec: &NamespaceSpec) -> Result<(), DomainError> {
        let labels = default_labels(spec);
        let label_args: Vec<String> = labels
            .iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect();

        let (code, _, stderr) = self
            .run(
                &[
                    "create",
                    "namespace",
                    &spec.namespace,
                ],
                Duration::from_secs(30),
            )
            .await?;
        if code != 0 && !stderr.contains("AlreadyExists") {
            return Err(DomainError::ClusterUnavailable(stderr));
        }

        for label in &label_args {
            let _ = self
                .run(
                    &["label", "namespace", &spec.namespace, label, "--overwrite"],
                    Duration::from_secs(15),
                )
                .await?;
        }

        let isolation = isolation_manifest(spec);
        apply_yaml(self, &spec.namespace, &isolation).await?;
        Ok(())
    }

    async fn destroy_namespace(&self, namespace: &str) -> Result<DestroyOutcome, DomainError> {
        let (code, _, stderr) = self
            .run(
                &["delete", "namespace", namespace, "--wait=false", "--ignore-not-found=true"],
                Duration::from_secs(60),
            )
            .await?;
        if code != 0 {
            return Err(DomainError::ClusterUnavailable(stderr));
        }
        if stderr.contains("NotFound") {
            Ok(DestroyOutcome::AlreadyDestroyed)
        } else {
            Ok(DestroyOutcome::Destroyed)
        }
    }

    async fn apply_manifests(
        &self,
        namespace: &str,
        rendered_yaml: &str,
        timeout_d: Duration,
    ) -> Result<ApplyResult, DomainError> {
        apply_yaml(self, namespace, rendered_yaml).await?;
        let resources = list_resources_from_yaml(rendered_yaml);
        let image_refs = crate::render::common::extract_images(rendered_yaml);
        // Best-effort wait
        let _ = timeout_d;
        Ok(ApplyResult {
            resources,
            image_refs,
        })
    }

    async fn observe_workload(
        &self,
        namespace: &str,
        max: Duration,
    ) -> Result<WorkloadObservation, DomainError> {
        let (code, stdout, stderr) = self
            .run(
                &[
                    "get",
                    "events",
                    "-n",
                    namespace,
                    "-o",
                    "json",
                ],
                max,
            )
            .await?;
        if code != 0 {
            return Err(DomainError::ObservationFailed(stderr));
        }
        let events = parse_events_json(&stdout);

        let (code, pods_json, stderr) = self
            .run(&["get", "pods", "-n", namespace, "-o", "json"], max)
            .await?;
        if code != 0 {
            return Err(DomainError::ObservationFailed(stderr));
        }
        let pods = parse_pods_json(&pods_json);

        Ok(WorkloadObservation {
            events,
            pods,
            rendered_hint: None,
        })
    }

    async fn check_rollout(
        &self,
        namespace: &str,
        resource: &str,
        max: Duration,
    ) -> Result<RolloutStatus, DomainError> {
        let timeout_s = max.as_secs().max(1).to_string();
        let (code, stdout, stderr) = self
            .run(
                &[
                    "rollout",
                    "status",
                    resource,
                    "-n",
                    namespace,
                    "--timeout",
                    &format!("{timeout_s}s"),
                ],
                max + Duration::from_secs(5),
            )
            .await?;
        Ok(RolloutStatus {
            ready: code == 0,
            message: if code == 0 { stdout } else { stderr },
        })
    }

    async fn http_health(
        &self,
        _namespace: &str,
        url: &str,
        expected_status: i32,
        max: Duration,
    ) -> Result<HttpHealthResult, DomainError> {
        // In-cluster URLs are not reachable from controller host without port-forward.
        // Fail closed for mandatory checks when we cannot reach them from kubectl backend
        // unless URL is localhost / loopback.
        if !(url.contains("127.0.0.1") || url.contains("localhost")) {
            return Err(DomainError::ValidationUnavailable(format!(
                "http health to {url} requires in-cluster probe or port-forward; fail closed"
            )));
        }
        let client = tokio::time::timeout(max, async {
            // Minimal fetch without extra deps: use kubectl run wget? Prefer reqwest-less approach via curl.
            let mut cmd = Command::new("curl");
            cmd.args(["-s", "-o", "/dev/null", "-w", "%{http_code}", url]);
            cmd.output().await
        })
        .await
        .map_err(|_| DomainError::Timeout(format!("curl {url}")))?
        .map_err(|e| DomainError::ValidationUnavailable(e.to_string()))?;

        let code_str = String::from_utf8_lossy(&client.stdout).trim().to_string();
        let status_code = code_str.parse::<i32>().ok();
        let ok = status_code == Some(expected_status);
        Ok(HttpHealthResult {
            ok,
            status_code,
            message: format!("curl {url} => {code_str}"),
        })
    }
}

async fn apply_yaml(
    cluster: &KubectlCluster,
    namespace: &str,
    yaml: &str,
) -> Result<(), DomainError> {
    let tmp = tempfile::NamedTempFile::new()
        .map_err(|e| DomainError::Internal(e.to_string()))?;
    std::fs::write(tmp.path(), yaml).map_err(|e| DomainError::Internal(e.to_string()))?;
    let path = tmp.path().to_string_lossy().to_string();
    let (code, _, stderr) = cluster
        .run(
            &["apply", "-n", namespace, "-f", &path],
            Duration::from_secs(60),
        )
        .await?;
    if code != 0 {
        return Err(DomainError::DeployFailed(stderr));
    }
    Ok(())
}

fn isolation_manifest(spec: &NamespaceSpec) -> String {
    format!(
        r#"apiVersion: v1
kind: ResourceQuota
metadata:
  name: raphael-quota
  namespace: {ns}
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 2Gi
    limits.cpu: "2"
    limits.memory: 2Gi
    pods: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: raphael-limits
  namespace: {ns}
spec:
  limits:
    - type: Container
      default:
        cpu: 250m
        memory: 256Mi
      defaultRequest:
        cpu: 50m
        memory: 64Mi
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {sa}
  namespace: {ns}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: {ns}
spec:
  podSelector: {{}}
  policyTypes:
    - Ingress
    - Egress
"#,
        ns = spec.namespace,
        sa = spec.service_account
    )
}

fn list_resources_from_yaml(yaml: &str) -> Vec<ResourceRef> {
    crate::render::common::list_resources(yaml)
}

fn parse_events_json(raw: &str) -> Vec<ObservedEvent> {
    let Ok(v) = serde_json::from_str::<serde_json::Value>(raw) else {
        return vec![];
    };
    v.get("items")
        .and_then(|i| i.as_array())
        .map(|items| {
            items
                .iter()
                .map(|item| ObservedEvent {
                    reason: item
                        .get("reason")
                        .and_then(|x| x.as_str())
                        .unwrap_or("")
                        .to_string(),
                    message: item
                        .get("message")
                        .and_then(|x| x.as_str())
                        .unwrap_or("")
                        .to_string(),
                    involved_kind: item
                        .pointer("/involvedObject/kind")
                        .and_then(|x| x.as_str())
                        .unwrap_or("")
                        .to_string(),
                    involved_name: item
                        .pointer("/involvedObject/name")
                        .and_then(|x| x.as_str())
                        .unwrap_or("")
                        .to_string(),
                })
                .collect()
        })
        .unwrap_or_default()
}

fn parse_pods_json(raw: &str) -> Vec<ObservedPod> {
    let Ok(v) = serde_json::from_str::<serde_json::Value>(raw) else {
        return vec![];
    };
    v.get("items")
        .and_then(|i| i.as_array())
        .map(|items| {
            items
                .iter()
                .map(|item| {
                    let name = item
                        .pointer("/metadata/name")
                        .and_then(|x| x.as_str())
                        .unwrap_or("pod")
                        .to_string();
                    let phase = item
                        .pointer("/status/phase")
                        .and_then(|x| x.as_str())
                        .unwrap_or("Unknown")
                        .to_string();
                    let container_statuses = item
                        .pointer("/status/containerStatuses")
                        .and_then(|x| x.as_array())
                        .map(|arr| {
                            arr.iter()
                                .map(|c| ObservedContainerStatus {
                                    name: c
                                        .get("name")
                                        .and_then(|x| x.as_str())
                                        .unwrap_or("app")
                                        .to_string(),
                                    ready: c.get("ready").and_then(|x| x.as_bool()).unwrap_or(false),
                                    restart_count: c
                                        .get("restartCount")
                                        .and_then(|x| x.as_i64())
                                        .unwrap_or(0) as i32,
                                    waiting_reason: c
                                        .pointer("/state/waiting/reason")
                                        .and_then(|x| x.as_str())
                                        .map(|s| s.to_string()),
                                    waiting_message: c
                                        .pointer("/state/waiting/message")
                                        .and_then(|x| x.as_str())
                                        .map(|s| s.to_string()),
                                    last_termination_reason: c
                                        .pointer("/lastState/terminated/reason")
                                        .and_then(|x| x.as_str())
                                        .map(|s| s.to_string()),
                                    image: c
                                        .get("image")
                                        .and_then(|x| x.as_str())
                                        .map(|s| s.to_string()),
                                })
                                .collect()
                        })
                        .unwrap_or_default();
                    ObservedPod {
                        name,
                        phase,
                        container_statuses,
                    }
                })
                .collect()
        })
        .unwrap_or_default()
}
