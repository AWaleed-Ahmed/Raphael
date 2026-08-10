use std::collections::HashMap;
use std::sync::RwLock;
use std::time::Duration;

use async_trait::async_trait;
use serde_yaml::Value;

use crate::domain::errors::DomainError;
use crate::domain::models::ResourceRef;
use crate::k8s::{
    ApplyResult, ClusterBackend, DestroyOutcome, HttpHealthResult, NamespaceSpec, ObservedContainerStatus,
    ObservedEvent, ObservedPod, RolloutStatus, WorkloadObservation,
};
use crate::observe::signatures::analyze_rendered_yaml;

#[derive(Default)]
struct MockNs {
    exists: bool,
    rendered_yaml: Option<String>,
    healthy_override: bool,
}

pub struct MockCluster {
    namespaces: RwLock<HashMap<String, MockNs>>,
}

impl MockCluster {
    pub fn new() -> Self {
        Self {
            namespaces: RwLock::new(HashMap::new()),
        }
    }
}

impl Default for MockCluster {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ClusterBackend for MockCluster {
    fn name(&self) -> &'static str {
        "mock"
    }

    async fn create_isolated_namespace(&self, spec: &NamespaceSpec) -> Result<(), DomainError> {
        let mut guard = self
            .namespaces
            .write()
            .map_err(|_| DomainError::Internal("mock lock poisoned".into()))?;
        if let Some(existing) = guard.get(&spec.namespace) {
            if existing.exists {
                return Err(DomainError::Conflict(format!(
                    "namespace already exists: {}",
                    spec.namespace
                )));
            }
        }
        guard.insert(
            spec.namespace.clone(),
            MockNs {
                exists: true,
                rendered_yaml: None,
                healthy_override: false,
            },
        );
        tracing::info!(
            namespace = %spec.namespace,
            sandbox_id = %spec.sandbox_id,
            "mock: created isolated namespace with quota/netpol/sa"
        );
        Ok(())
    }

    async fn destroy_namespace(&self, namespace: &str) -> Result<DestroyOutcome, DomainError> {
        let mut guard = self
            .namespaces
            .write()
            .map_err(|_| DomainError::Internal("mock lock poisoned".into()))?;
        match guard.get_mut(namespace) {
            Some(ns) if ns.exists => {
                ns.exists = false;
                ns.rendered_yaml = None;
                Ok(DestroyOutcome::Destroyed)
            }
            Some(_) | None => Ok(DestroyOutcome::AlreadyDestroyed),
        }
    }

    async fn apply_manifests(
        &self,
        namespace: &str,
        rendered_yaml: &str,
        _timeout: Duration,
    ) -> Result<ApplyResult, DomainError> {
        let mut guard = self
            .namespaces
            .write()
            .map_err(|_| DomainError::Internal("mock lock poisoned".into()))?;
        let ns = guard
            .get_mut(namespace)
            .ok_or_else(|| DomainError::NotFound(format!("namespace not found: {namespace}")))?;
        if !ns.exists {
            return Err(DomainError::NotFound(format!(
                "namespace destroyed: {namespace}"
            )));
        }
        let resources = parse_resources(rendered_yaml)?;
        let image_refs = extract_images(rendered_yaml);
        // If rendered YAML no longer matches a known failure, mark healthy for validation paths.
        let sig = analyze_rendered_yaml(rendered_yaml);
        ns.healthy_override = sig.as_ref().map(|s| s.class == "healthy").unwrap_or(false)
            || sig.is_none();
        // Keep failure state when analyzer finds a failure class.
        if let Some(s) = &sig {
            if s.class != "healthy" {
                ns.healthy_override = false;
            }
        }
        ns.rendered_yaml = Some(rendered_yaml.to_string());
        Ok(ApplyResult {
            resources,
            image_refs,
        })
    }

    async fn observe_workload(
        &self,
        namespace: &str,
        _timeout: Duration,
    ) -> Result<WorkloadObservation, DomainError> {
        let guard = self
            .namespaces
            .read()
            .map_err(|_| DomainError::Internal("mock lock poisoned".into()))?;
        let ns = guard
            .get(namespace)
            .ok_or_else(|| DomainError::NotFound(format!("namespace not found: {namespace}")))?;
        if !ns.exists {
            return Err(DomainError::NotFound(format!(
                "namespace destroyed: {namespace}"
            )));
        }
        let yaml = ns
            .rendered_yaml
            .clone()
            .ok_or_else(|| DomainError::ObservationFailed("no revision deployed".into()))?;

        if ns.healthy_override {
            return Ok(WorkloadObservation {
                events: vec![],
                pods: vec![ObservedPod {
                    name: "demo-0".into(),
                    phase: "Running".into(),
                    container_statuses: vec![ObservedContainerStatus {
                        name: "app".into(),
                        ready: true,
                        restart_count: 0,
                        waiting_reason: None,
                        waiting_message: None,
                        last_termination_reason: None,
                        image: Some("ghcr.io/raphael/demo:1.0.0".into()),
                    }],
                }],
                rendered_hint: Some(yaml),
            });
        }

        let synthetic = synthesize_from_yaml(&yaml);
        Ok(WorkloadObservation {
            events: synthetic.events,
            pods: synthetic.pods,
            rendered_hint: Some(yaml),
        })
    }

    async fn check_rollout(
        &self,
        namespace: &str,
        resource: &str,
        _timeout: Duration,
    ) -> Result<RolloutStatus, DomainError> {
        let obs = self.observe_workload(namespace, Duration::from_secs(1)).await?;
        let ready = obs.pods.iter().all(|p| {
            p.phase == "Running" && p.container_statuses.iter().all(|c| c.ready)
        });
        Ok(RolloutStatus {
            ready,
            message: if ready {
                format!("{resource} ready in mock backend")
            } else {
                format!("{resource} not ready in mock backend")
            },
        })
    }

    async fn http_health(
        &self,
        namespace: &str,
        url: &str,
        expected_status: i32,
        _timeout: Duration,
    ) -> Result<HttpHealthResult, DomainError> {
        let rollout = self
            .check_rollout(namespace, "deployment/demo", Duration::from_secs(1))
            .await?;
        if rollout.ready {
            Ok(HttpHealthResult {
                ok: true,
                status_code: Some(expected_status),
                message: format!("mock http {url} => {expected_status}"),
            })
        } else {
            Ok(HttpHealthResult {
                ok: false,
                status_code: Some(503),
                message: format!("mock http {url} unavailable while workload unhealthy"),
            })
        }
    }
}

struct SyntheticObs {
    events: Vec<ObservedEvent>,
    pods: Vec<ObservedPod>,
}

fn synthesize_from_yaml(yaml: &str) -> SyntheticObs {
    if let Some(sig) = analyze_rendered_yaml(yaml) {
        match sig.class.as_str() {
            "probe_misconfiguration" => {
                return SyntheticObs {
                    events: vec![ObservedEvent {
                        reason: "Unhealthy".into(),
                        message: sig
                            .summary
                            .clone()
                            .unwrap_or_else(|| "Readiness probe failed".into()),
                        involved_kind: sig.resource_kind.clone(),
                        involved_name: sig.resource_name.clone(),
                    }],
                    pods: vec![ObservedPod {
                        name: format!("{}-0", sig.resource_name),
                        phase: "Running".into(),
                        container_statuses: vec![ObservedContainerStatus {
                            name: sig.container.clone().unwrap_or_else(|| "app".into()),
                            ready: false,
                            restart_count: 3,
                            waiting_reason: None,
                            waiting_message: None,
                            last_termination_reason: None,
                            image: Some("ghcr.io/raphael/demo:1.0.0".into()),
                        }],
                    }],
                };
            }
            "bad_image_reference" => {
                return SyntheticObs {
                    events: vec![ObservedEvent {
                        reason: "Failed".into(),
                        message: "Failed to pull image".into(),
                        involved_kind: "Pod".into(),
                        involved_name: sig.resource_name.clone(),
                    }],
                    pods: vec![ObservedPod {
                        name: format!("{}-0", sig.resource_name),
                        phase: "Pending".into(),
                        container_statuses: vec![ObservedContainerStatus {
                            name: "app".into(),
                            ready: false,
                            restart_count: 0,
                            waiting_reason: Some("ImagePullBackOff".into()),
                            waiting_message: sig.message.clone(),
                            last_termination_reason: None,
                            image: sig
                                .attributes
                                .get("image")
                                .and_then(|v| v.as_str())
                                .map(|s| s.to_string()),
                        }],
                    }],
                };
            }
            "invalid_missing_config" => {
                return SyntheticObs {
                    events: vec![ObservedEvent {
                        reason: "Failed".into(),
                        message: "Error: configmap key not found".into(),
                        involved_kind: "Pod".into(),
                        involved_name: sig.resource_name.clone(),
                    }],
                    pods: vec![ObservedPod {
                        name: format!("{}-0", sig.resource_name),
                        phase: "Pending".into(),
                        container_statuses: vec![ObservedContainerStatus {
                            name: "app".into(),
                            ready: false,
                            restart_count: 0,
                            waiting_reason: Some("CreateContainerConfigError".into()),
                            waiting_message: sig.message.clone(),
                            last_termination_reason: None,
                            image: Some("ghcr.io/raphael/demo:1.0.0".into()),
                        }],
                    }],
                };
            }
            "service_port_mismatch" => {
                return SyntheticObs {
                    events: vec![ObservedEvent {
                        reason: "ConnectionRefused".into(),
                        message: "service targetPort mismatch".into(),
                        involved_kind: "Service".into(),
                        involved_name: sig.resource_name.clone(),
                    }],
                    pods: vec![ObservedPod {
                        name: "demo-0".into(),
                        phase: "Running".into(),
                        container_statuses: vec![ObservedContainerStatus {
                            name: "app".into(),
                            ready: true,
                            restart_count: 0,
                            waiting_reason: None,
                            waiting_message: None,
                            last_termination_reason: None,
                            image: Some("ghcr.io/raphael/demo:1.0.0".into()),
                        }],
                    }],
                };
            }
            "resource_constraint" => {
                return SyntheticObs {
                    events: vec![ObservedEvent {
                        reason: "OOMKilled".into(),
                        message: "Container killed due to memory limit".into(),
                        involved_kind: "Pod".into(),
                        involved_name: sig.resource_name.clone(),
                    }],
                    pods: vec![ObservedPod {
                        name: format!("{}-0", sig.resource_name),
                        phase: "Running".into(),
                        container_statuses: vec![ObservedContainerStatus {
                            name: "app".into(),
                            ready: false,
                            restart_count: 5,
                            waiting_reason: None,
                            waiting_message: None,
                            last_termination_reason: Some("OOMKilled".into()),
                            image: Some("ghcr.io/raphael/demo:1.0.0".into()),
                        }],
                    }],
                };
            }
            _ => {}
        }
    }

    SyntheticObs {
        events: vec![],
        pods: vec![ObservedPod {
            name: "demo-0".into(),
            phase: "Running".into(),
            container_statuses: vec![ObservedContainerStatus {
                name: "app".into(),
                ready: true,
                restart_count: 0,
                waiting_reason: None,
                waiting_message: None,
                last_termination_reason: None,
                image: Some("ghcr.io/raphael/demo:1.0.0".into()),
            }],
        }],
    }
}

fn parse_resources(yaml: &str) -> Result<Vec<ResourceRef>, DomainError> {
    let mut out = Vec::new();
    for doc in serde_yaml::Deserializer::from_str(yaml) {
        let value = Value::deserialize(doc).map_err(|e| DomainError::DeployFailed(e.to_string()))?;
        if value.is_null() {
            continue;
        }
        let kind = value
            .get("kind")
            .and_then(|v| v.as_str())
            .unwrap_or("Unknown")
            .to_string();
        let name = value
            .get("metadata")
            .and_then(|m| m.get("name"))
            .and_then(|v| v.as_str())
            .unwrap_or("unnamed")
            .to_string();
        let api_version = value
            .get("apiVersion")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        out.push(ResourceRef {
            kind,
            name,
            api_version,
        });
    }
    Ok(out)
}

fn extract_images(yaml: &str) -> Vec<String> {
    let mut images = Vec::new();
    for doc in serde_yaml::Deserializer::from_str(yaml) {
        let Ok(value) = Value::deserialize(doc) else {
            continue;
        };
        collect_images(&value, &mut images);
    }
    images.sort();
    images.dedup();
    images
}

fn collect_images(value: &Value, out: &mut Vec<String>) {
    match value {
        Value::Mapping(map) => {
            if let Some(Value::String(img)) = map.get(Value::String("image".into())) {
                out.push(img.clone());
            }
            for v in map.values() {
                collect_images(v, out);
            }
        }
        Value::Sequence(seq) => {
            for v in seq {
                collect_images(v, out);
            }
        }
        _ => {}
    }
}

use serde::Deserialize;
