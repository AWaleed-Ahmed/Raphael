//! Raphael sandbox controller library.
//!
//! Layers: `api` → `domain` → adapters (`k8s`, `render`, `observe`, `validate`, `cleanup`, `policy`).

pub mod api;
pub mod cleanup;
pub mod domain;
pub mod k8s;
pub mod observe;
pub mod policy;
pub mod render;
pub mod state;
pub mod validate;

pub use domain::service::SandboxService;
