export const stages = [
  {
    label: "01 / Investigate",
    title: "A mismatch worth investigating.",
    scope: "Read-only investigation",
    copy: "The container listens on 8080. The readiness probe targets 8081. Correlate the event and manifest before proposing a repair.",
    file: "events + deployment.yaml",
    badge: "Candidate cause",
    result: "Two sources. One testable hypothesis.",
    lines: [
      ["", "Warning  Unhealthy  payments-api"],
      ["removed", "GET :8081/healthz → connection refused"],
      ["", "containerPort: 8080"],
      ["emphasis", "readinessProbe.httpGet.port: 8081"],
    ],
  },
  {
    label: "02 / Reproduce",
    title: "Same failure. Isolated environment.",
    scope: "Ignis / isolated sandbox",
    copy: "Deploy the failing revision in an Ignis sandbox. A matching failure signature establishes the baseline for testing the candidate repair.",
    file: "sandbox / baseline observation",
    badge: "Failure reproduced",
    result: "A matching signature establishes the baseline.",
    lines: [
      ["", "revision: failing deployment"],
      ["", "environment: isolated sandbox"],
      ["removed", "readiness check: connection refused"],
      ["emphasis", "failure signature: matched"],
    ],
  },
  {
    label: "03 / Patch",
    title: "One field. A focused repair.",
    scope: "Ignis / isolated sandbox",
    copy: "Point the readiness probe at the declared container port. Test this narrow configuration change in the sandbox before preparing it for review.",
    file: "deploy/deployment.yaml",
    badge: "Candidate patch",
    result: "A small diff that a human can inspect.",
    lines: [
      ["", "readinessProbe:"],
      ["", "  httpGet:"],
      ["", "    path: /healthz"],
      ["removed", "−   port: 8081"],
      ["added", "+   port: 8080"],
    ],
  },
  {
    label: "04 / Validate",
    title: "The checks travel with the change.",
    scope: "Sandbox validation only",
    copy: "Compare the baseline with the patched run. Attach the named checks and their scope. Missing mandatory checks stop the workflow.",
    file: "validation / before + after",
    badge: "Evidence attached",
    result: "Sandbox evidence, not production verification.",
    lines: [
      ["", "before: failure signature reproduced"],
      ["added", "after: original signature absent"],
      ["added", "mandatory sandbox checks: complete"],
      ["emphasis", "scope: isolated sandbox only"],
    ],
  },
  {
    label: "05 / Prepare draft",
    title: "Package the repair with its evidence.",
    scope: "Reviewable draft preparation",
    copy: "Bring the narrow diff, reproduced failure, and sandbox validation into one draft. Live draft publishing remains opt-in.",
    file: "draft / evidence bundle",
    badge: "Draft prepared",
    result: "A reviewable handoff, with the scope made explicit.",
    lines: [
      ["", "change: align probe with container port"],
      ["added", "baseline + validation: attached"],
      ["emphasis", "delivery: draft pull request"],
      ["", "production: unchanged"],
    ],
  },
  {
    label: "06 / Human review",
    title: "The final decision belongs to you.",
    scope: "Human-controlled delivery",
    copy: "Review the proposed diff alongside its evidence and validation scope. Check the proposed change against your deployment process.",
    file: "draft / readiness probe repair",
    badge: "Awaiting review",
    result: "Draft status and validation scope are attached.",
    lines: [
      ["", "change: align probe with container port"],
      ["", "attachments: evidence + validation"],
      ["emphasis", "status: draft · awaiting human review"],
      ["", "merge: not performed"],
      ["", "production: unchanged"],
    ],
  },
];

export const validationExamples = {
  passing: {
    rows: [
      ["check", "Before / reproduced failure"],
      ["check", "After / signature absent"],
      ["arrow-elbow-down-right", "Scope / sandbox checks only"],
    ],
    notice:
      "Sandbox evidence is attached to the draft. Production has not been changed.",
  },
  blocked: {
    rows: [
      ["check", "Before / reproduced failure"],
      ["warning", "Rollout check / unavailable"],
      ["pause", "Delivery / no draft prepared"],
    ],
    notice:
      "A mandatory check could not run. Validation is inconclusive; the workflow stops and reports the gap for human investigation.",
  },
};
