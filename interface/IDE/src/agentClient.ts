/** Thin HTTP client for the local Raphael agent (I0). Never calls the sandbox. */

export type RunSummary = {
  run_id: string;
  status: string;
  repository: { owner: string; name: string };
  commit_sha: string;
  created_at?: string;
  updated_at?: string;
  terminal_reason?: string | null;
  failure_class?: string | null;
  pull_request_url?: string | null;
  trigger_kind?: string | null;
};

export type RunRecord = Record<string, unknown> & {
  run_id: string;
  status: string;
  pull_request_url?: string | null;
  issue_comment_url?: string | null;
  candidate_patches?: Array<Record<string, unknown>>;
  active_patch_id?: string | null;
  publish?: Record<string, unknown>;
  fix_rules?: { writable_path_prefixes?: string[] };
  diagnosis?: {
    classification?: { failure_class?: string };
    confidence?: number;
  };
};

export class AgentClientError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly body?: unknown
  ) {
    super(message);
    this.name = "AgentClientError";
  }
}

export class AgentClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token?: string
  ) {}

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };
    if (this.token) {
      h.Authorization = `Bearer ${this.token}`;
    }
    return h;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.baseUrl.replace(/\/$/, "")}${path}`;
    let res: Response;
    try {
      res = await fetch(url, {
        method,
        headers: this.headers(),
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (err) {
      throw new AgentClientError(
        `agent unreachable at ${this.baseUrl}: ${String(err)}`
      );
    }
    const text = await res.text();
    let parsed: unknown = null;
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
    }
    if (!res.ok) {
      const msg =
        typeof parsed === "object" &&
        parsed &&
        "error" in parsed &&
        typeof (parsed as { error?: { message?: string } }).error?.message ===
          "string"
          ? (parsed as { error: { message: string } }).error.message
          : `HTTP ${res.status}`;
      throw new AgentClientError(msg, res.status, parsed);
    }
    return parsed as T;
  }

  health(): Promise<{ ok?: boolean; service?: string }> {
    return this.request("GET", "/health");
  }

  goNogo(): Promise<{ go?: boolean; recommendation?: string }> {
    return this.request("GET", "/v1/pilot/go-nogo");
  }

  listRuns(params?: {
    owner?: string;
    repo?: string;
    limit?: number;
  }): Promise<{ runs: RunSummary[]; limit: number; next_cursor: string | null }> {
    const q = new URLSearchParams();
    if (params?.owner) q.set("owner", params.owner);
    if (params?.repo) q.set("repo", params.repo);
    q.set("limit", String(params?.limit ?? 20));
    const qs = q.toString();
    return this.request("GET", `/v1/runs?${qs}`);
  }

  getRun(runId: string): Promise<RunRecord> {
    return this.request("GET", `/v1/runs/${encodeURIComponent(runId)}`);
  }

  feedback(
    runId: string,
    outcome: "accepted" | "rejected" | "edited",
    notes?: string
  ): Promise<Record<string, unknown>> {
    const actionId = `ide-fb-${Date.now().toString(36)}-${Math.random()
      .toString(36)
      .slice(2, 8)}`;
    return this.request("POST", `/v1/runs/${encodeURIComponent(runId)}/actions`, {
      verb: "feedback",
      action_id: actionId,
      outcome,
      notes,
    });
  }
}
