pub mod kubectl;
pub mod mock;
pub mod types;

use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;

use crate::domain::errors::DomainError;
use crate::domain::models::ResourceRef;

pub use types::*;

#[async_trait]
pub trait ClusterBackend: Send + Sync {
    fn name(&self) -> &'static str;

    async fn create_isolated_namespace(
        &self,
        spec: &NamespaceSpec,
    ) -> Result<(), DomainError>;

    async fn destroy_namespace(&self, namespace: &str) -> Result<DestroyOutcome, DomainError>;

    async fn apply_manifests(
        &self,
        namespace: &str,
        rendered_yaml: &str,
        timeout: Duration,
    ) -> Result<ApplyResult, DomainError>;

    async fn observe_workload(
        &self,
        namespace: &str,
        timeout: Duration,
    ) -> Result<WorkloadObservation, DomainError>;

    async fn check_rollout(
        &self,
        namespace: &str,
        resource: &str,
        timeout: Duration,
    ) -> Result<RolloutStatus, DomainError>;

    async fn http_health(
        &self,
        namespace: &str,
        url: &str,
        expected_status: i32,
        timeout: Duration,
    ) -> Result<HttpHealthResult, DomainError>;
}

pub fn create_backend(name: &str) -> anyhow::Result<Arc<dyn ClusterBackend>> {
    match name {
        "mock" => Ok(Arc::new(mock::MockCluster::new())),
        "kind" | "kubeconfig" | "kubectl" => Ok(Arc::new(kubectl::KubectlCluster::from_env()?)),
        other => anyhow::bail!("unknown RAPHAEL_CLUSTER_BACKEND: {other}"),
    }
}

#[derive(Debug, Clone)]
pub struct ApplyResult {
    pub resources: Vec<ResourceRef>,
    pub image_refs: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DestroyOutcome {
    Destroyed,
    AlreadyDestroyed,
}
