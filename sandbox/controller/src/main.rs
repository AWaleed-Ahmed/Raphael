use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use raphael_sandbox_controller::api::router;
use raphael_sandbox_controller::cleanup::ttl::TtlReaper;
use raphael_sandbox_controller::domain::service::SandboxService;
use raphael_sandbox_controller::k8s::{create_backend, ClusterBackend};
use raphael_sandbox_controller::state::registry::SandboxRegistry;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse()?))
        .json()
        .init();

    let backend_name = env::var("RAPHAEL_CLUSTER_BACKEND").unwrap_or_else(|_| "mock".into());
    let backend: Arc<dyn ClusterBackend> = create_backend(&backend_name)?;
    let registry = Arc::new(SandboxRegistry::new());
    let service = Arc::new(SandboxService::new(backend.clone(), registry.clone()));

    let reaper = TtlReaper::new(service.clone(), Duration::from_secs(30));
    tokio::spawn(async move {
        reaper.run().await;
    });

    let app = router(service);
    let addr: SocketAddr = env::var("RAPHAEL_LISTEN")
        .unwrap_or_else(|_| "127.0.0.1:8080".into())
        .parse()?;

    tracing::info!(%addr, backend = %backend_name, "sandbox controller listening");
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
