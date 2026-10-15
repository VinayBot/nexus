/* Generated from backend/nexus/core/event_types.py by `make types`. Do not edit. */

export type NexusEvent =
  | MissionCreatedEvent
  | MissionStartedEvent
  | MissionCompletedEvent
  | MissionFailedEvent
  | MissionCancelledEvent
  | NodeEnteredEvent
  | NodeExitedEvent
  | EdgeTakenEvent
  | SendFanoutEvent
  | SendFaninEvent
  | ReducerMergedEvent
  | HandoffEvent
  | CheckpointSavedEvent
  | PlanCreatedEvent
  | AgentAssignedEvent
  | AgentThinkingEvent
  | AgentTokenEvent
  | AgentActionEvent
  | AgentObservationEvent
  | AgentFinalEvent
  | AgentStatusEvent
  | ToolCalledEvent
  | ToolResultEvent
  | CouncilProposalEvent
  | CouncilMaskedEvent
  | CouncilReviewEvent
  | CouncilRoundEvent
  | CouncilVerdictEvent
  | SandboxTestResultEvent
  | RetryEvent
  | CircuitStateEvent
  | LlmRoutedEvent
  | LlmCallEvent
  | DeadLetterEvent
  | MemoryPrunedEvent
  | MemorySummarisedEvent
  | MemoryStoredEvent
  | MemoryRecalledEvent
  | RiskScoredEvent
  | GuardrailTriggeredEvent
  | InterruptRaisedEvent
  | InterruptResolvedEvent
  | EmailSentEvent
  | TimetravelForkEvent
  | GovernorMetricsEvent
  | IncidentDetectedEvent
  | ChaosToggledEvent
  | ServiceHealthEvent;
export type Id = string;
export type Seq = number;
export type MissionId = string | null;
export type ThreadId = string | null;
export type CheckpointId = string | null;
export type Ts = number;
export type AgentId = string | null;
export type Node = string | null;
export type Type = "mission.created";
export type Title = string;
export type Playbook = string | null;
export type Task = string;
export type Id1 = string;
export type Seq1 = number;
export type MissionId1 = string | null;
export type ThreadId1 = string | null;
export type CheckpointId1 = string | null;
export type Ts1 = number;
export type AgentId1 = string | null;
export type Node1 = string | null;
export type Type1 = "mission.started";
export type Resumed = boolean;
export type Id2 = string;
export type Seq2 = number;
export type MissionId2 = string | null;
export type ThreadId2 = string | null;
export type CheckpointId2 = string | null;
export type Ts2 = number;
export type AgentId2 = string | null;
export type Node2 = string | null;
export type Type2 = "mission.completed";
export type Outcome = "success" | "rejected" | "blocked" | "rolled_back" | "partial";
export type Summary = string;
export type Id3 = string;
export type Seq3 = number;
export type MissionId3 = string | null;
export type ThreadId3 = string | null;
export type CheckpointId3 = string | null;
export type Ts3 = number;
export type AgentId3 = string | null;
export type Node3 = string | null;
export type Type3 = "mission.failed";
export type Error = string;
export type Node4 = string | null;
export type Id4 = string;
export type Seq4 = number;
export type MissionId4 = string | null;
export type ThreadId4 = string | null;
export type CheckpointId4 = string | null;
export type Ts4 = number;
export type AgentId4 = string | null;
export type Node5 = string | null;
export type Type4 = "mission.cancelled";
export type Reason = string;
export type Id5 = string;
export type Seq5 = number;
export type MissionId5 = string | null;
export type ThreadId5 = string | null;
export type CheckpointId5 = string | null;
export type Ts5 = number;
export type AgentId5 = string | null;
export type Node6 = string | null;
export type Type5 = "node.entered";
export type Node7 = string;
export type Step = number | null;
export type Id6 = string;
export type Seq6 = number;
export type MissionId6 = string | null;
export type ThreadId6 = string | null;
export type CheckpointId6 = string | null;
export type Ts6 = number;
export type AgentId6 = string | null;
export type Node8 = string | null;
export type Type6 = "node.exited";
export type Node9 = string;
export type DurationMs = number;
export type Status = "ok" | "error" | "interrupted";
/**
 * State keys the node wrote.
 */
export type Updated = string[];
export type Id7 = string;
export type Seq7 = number;
export type MissionId7 = string | null;
export type ThreadId7 = string | null;
export type CheckpointId7 = string | null;
export type Ts7 = number;
export type AgentId7 = string | null;
export type Node10 = string | null;
export type Type7 = "edge.taken";
export type Source = string;
export type Target = string;
export type Label = string;
export type Id8 = string;
export type Seq8 = number;
export type MissionId8 = string | null;
export type ThreadId8 = string | null;
export type CheckpointId8 = string | null;
export type Ts8 = number;
export type AgentId8 = string | null;
export type Node11 = string | null;
export type Type8 = "send.fanout";
export type Source1 = string;
export type Target1 = string;
export type Count = number;
export type Items = string[];
export type Id9 = string;
export type Seq9 = number;
export type MissionId9 = string | null;
export type ThreadId9 = string | null;
export type CheckpointId9 = string | null;
export type Ts9 = number;
export type AgentId9 = string | null;
export type Node12 = string | null;
export type Type9 = "send.fanin";
export type Target2 = string;
export type Count1 = number;
export type Id10 = string;
export type Seq10 = number;
export type MissionId10 = string | null;
export type ThreadId10 = string | null;
export type CheckpointId10 = string | null;
export type Ts10 = number;
export type AgentId10 = string | null;
export type Node13 = string | null;
export type Type10 = "reducer.merged";
export type Channel = string;
export type Reducer = string;
export type Added = number;
export type Total = number;
export type Detail = string;
export type Id11 = string;
export type Seq11 = number;
export type MissionId11 = string | null;
export type ThreadId11 = string | null;
export type CheckpointId11 = string | null;
export type Ts11 = number;
export type AgentId11 = string | null;
export type Node14 = string | null;
export type Type11 = "handoff";
export type Source2 = string;
export type Target3 = string;
export type Reason1 = string;
export type Id12 = string;
export type Seq12 = number;
export type MissionId12 = string | null;
export type ThreadId12 = string | null;
export type CheckpointId12 = string | null;
export type Ts12 = number;
export type AgentId12 = string | null;
export type Node15 = string | null;
export type Type12 = "checkpoint.saved";
export type CheckpointId13 = string;
export type Step1 = number;
export type Next = string[];
export type Id13 = string;
export type Seq13 = number;
export type MissionId13 = string | null;
export type ThreadId13 = string | null;
export type CheckpointId14 = string | null;
export type Ts13 = number;
export type AgentId13 = string | null;
export type Node16 = string | null;
export type Type13 = "plan.created";
export type Steps = {
  [k: string]: unknown;
}[];
export type Revision = number;
export type Source3 = "llm" | "template";
export type Id14 = string;
export type Seq14 = number;
export type MissionId14 = string | null;
export type ThreadId14 = string | null;
export type CheckpointId15 = string | null;
export type Ts14 = number;
export type AgentId14 = string | null;
export type Node17 = string | null;
export type Type14 = "agent.assigned";
export type AgentId15 = string;
export type StepId = string | null;
export type Task1 = string;
export type Id15 = string;
export type Seq15 = number;
export type MissionId15 = string | null;
export type ThreadId15 = string | null;
export type CheckpointId16 = string | null;
export type Ts15 = number;
export type AgentId16 = string | null;
export type Node18 = string | null;
export type Type15 = "agent.thinking";
export type AgentId17 = string;
export type Text = string;
export type Iteration = number | null;
export type Id16 = string;
export type Seq16 = number;
export type MissionId16 = string | null;
export type ThreadId16 = string | null;
export type CheckpointId17 = string | null;
export type Ts16 = number;
export type AgentId18 = string | null;
export type Node19 = string | null;
export type Type16 = "agent.token";
export type AgentId19 = string;
export type Text1 = string;
export type Purpose = string;
export type Id17 = string;
export type Seq17 = number;
export type MissionId17 = string | null;
export type ThreadId17 = string | null;
export type CheckpointId18 = string | null;
export type Ts17 = number;
export type AgentId20 = string | null;
export type Node20 = string | null;
export type Type17 = "agent.action";
export type AgentId21 = string;
export type Tool = string;
export type Iteration1 = number | null;
export type Id18 = string;
export type Seq18 = number;
export type MissionId18 = string | null;
export type ThreadId18 = string | null;
export type CheckpointId19 = string | null;
export type Ts18 = number;
export type AgentId22 = string | null;
export type Node21 = string | null;
export type Type18 = "agent.observation";
export type AgentId23 = string;
export type Tool1 = string;
export type Summary1 = string;
export type Ok = boolean;
export type Id19 = string;
export type Seq19 = number;
export type MissionId19 = string | null;
export type ThreadId19 = string | null;
export type CheckpointId20 = string | null;
export type Ts19 = number;
export type AgentId24 = string | null;
export type Node22 = string | null;
export type Type19 = "agent.final";
export type AgentId25 = string;
export type Answer = string;
export type Id20 = string;
export type Seq20 = number;
export type MissionId20 = string | null;
export type ThreadId20 = string | null;
export type CheckpointId21 = string | null;
export type Ts20 = number;
export type AgentId26 = string | null;
export type Node23 = string | null;
export type Type20 = "agent.status";
export type AgentId27 = string;
export type Status1 = string;
export type Id21 = string;
export type Seq21 = number;
export type MissionId21 = string | null;
export type ThreadId21 = string | null;
export type CheckpointId22 = string | null;
export type Ts21 = number;
export type AgentId28 = string | null;
export type Node24 = string | null;
export type Type21 = "tool.called";
export type Server = string;
export type Tool2 = string;
export type CallId = string;
export type AgentId29 = string | null;
export type Id22 = string;
export type Seq22 = number;
export type MissionId22 = string | null;
export type ThreadId22 = string | null;
export type CheckpointId23 = string | null;
export type Ts22 = number;
export type AgentId30 = string | null;
export type Node25 = string | null;
export type Type22 = "tool.result";
export type Server1 = string;
export type Tool3 = string;
export type CallId1 = string;
export type Ok1 = boolean;
export type Summary2 = string;
export type DurationMs1 = number;
export type Id23 = string;
export type Seq23 = number;
export type MissionId23 = string | null;
export type ThreadId23 = string | null;
export type CheckpointId24 = string | null;
export type Ts23 = number;
export type AgentId31 = string | null;
export type Node26 = string | null;
export type Type23 = "council.proposal";
export type SolverId = string;
export type Strategy = string;
export type Summary3 = string;
export type Label1 = string | null;
export type Id24 = string;
export type Seq24 = number;
export type MissionId24 = string | null;
export type ThreadId24 = string | null;
export type CheckpointId25 = string | null;
export type Ts24 = number;
export type AgentId32 = string | null;
export type Node27 = string | null;
export type Type24 = "council.masked";
export type MappingHidden = boolean;
export type Labels = string[];
export type Id25 = string;
export type Seq25 = number;
export type MissionId25 = string | null;
export type ThreadId25 = string | null;
export type CheckpointId26 = string | null;
export type Ts25 = number;
export type AgentId33 = string | null;
export type Node28 = string | null;
export type Type25 = "council.review";
export type Reviewer = string;
export type TargetLabel = string;
export type Score = number;
export type Reason2 = string;
export type Id26 = string;
export type Seq26 = number;
export type MissionId26 = string | null;
export type ThreadId26 = string | null;
export type CheckpointId27 = string | null;
export type Ts26 = number;
export type AgentId34 = string | null;
export type Node29 = string | null;
export type Type26 = "council.round";
export type Round = number;
export type Divergence = number;
export type Converged = boolean;
export type Id27 = string;
export type Seq27 = number;
export type MissionId27 = string | null;
export type ThreadId27 = string | null;
export type CheckpointId28 = string | null;
export type Ts27 = number;
export type AgentId35 = string | null;
export type Node30 = string | null;
export type Type27 = "council.verdict";
export type Winner = string;
export type WinnerLabel = string;
export type RunnerUp = string | null;
export type Confidence = number;
export type Dissent = string;
export type Escalate = boolean;
export type Id28 = string;
export type Seq28 = number;
export type MissionId28 = string | null;
export type ThreadId28 = string | null;
export type CheckpointId29 = string | null;
export type Ts28 = number;
export type AgentId36 = string | null;
export type Node31 = string | null;
export type Type28 = "sandbox.test_result";
export type Target4 = string;
export type Passed = number;
export type Failed = number;
export type Errors = number;
export type Ok2 = boolean;
export type DurationMs2 = number;
export type Backend = string;
export type Summary4 = string;
export type Id29 = string;
export type Seq29 = number;
export type MissionId29 = string | null;
export type ThreadId29 = string | null;
export type CheckpointId30 = string | null;
export type Ts29 = number;
export type AgentId37 = string | null;
export type Node32 = string | null;
export type Type29 = "retry";
export type Layer = "transport" | "node" | "validation" | "fallback" | "tool";
export type Key = string;
export type Attempt = number;
export type MaxAttempts = number;
export type Reason3 = string;
export type AgentId38 = string | null;
export type Id30 = string;
export type Seq30 = number;
export type MissionId30 = string | null;
export type ThreadId30 = string | null;
export type CheckpointId31 = string | null;
export type Ts30 = number;
export type AgentId39 = string | null;
export type Node33 = string | null;
export type Type30 = "circuit.state";
export type Key1 = string;
export type State = "closed" | "open" | "half_open";
export type Failures = number;
export type Id31 = string;
export type Seq31 = number;
export type MissionId31 = string | null;
export type ThreadId31 = string | null;
export type CheckpointId32 = string | null;
export type Ts31 = number;
export type AgentId40 = string | null;
export type Node34 = string | null;
export type Type31 = "llm.routed";
export type Purpose1 = string;
export type Role = "main" | "fast" | "embed";
export type Model = string;
export type Reason4 = string;
export type Id32 = string;
export type Seq32 = number;
export type MissionId32 = string | null;
export type ThreadId32 = string | null;
export type CheckpointId33 = string | null;
export type Ts32 = number;
export type AgentId41 = string | null;
export type Node35 = string | null;
export type Type32 = "llm.call";
export type Model1 = string;
export type Purpose2 = string;
export type AgentId42 = string | null;
export type PromptTokens = number;
export type CompletionTokens = number;
export type EstimatedPromptTokens = number;
export type DurationMs3 = number;
export type TokensPerSec = number;
export type Id33 = string;
export type Seq33 = number;
export type MissionId33 = string | null;
export type ThreadId33 = string | null;
export type CheckpointId34 = string | null;
export type Ts33 = number;
export type AgentId43 = string | null;
export type Node36 = string | null;
export type Type33 = "dead_letter";
export type Node37 = string;
export type Error1 = string;
export type Attempts = number;
export type Id34 = string;
export type Seq34 = number;
export type MissionId34 = string | null;
export type ThreadId34 = string | null;
export type CheckpointId35 = string | null;
export type Ts34 = number;
export type AgentId44 = string | null;
export type Node38 = string | null;
export type Type34 = "memory.pruned";
export type AgentId45 = string;
export type Strategy1 = "sliding_window" | "summarise";
export type BeforeTokens = number;
export type AfterTokens = number;
export type DroppedMessages = number;
export type Budget = number;
export type Id35 = string;
export type Seq35 = number;
export type MissionId35 = string | null;
export type ThreadId35 = string | null;
export type CheckpointId36 = string | null;
export type Ts35 = number;
export type AgentId46 = string | null;
export type Node39 = string | null;
export type Type35 = "memory.summarised";
export type AgentId47 = string;
export type BeforeTokens1 = number;
export type AfterTokens1 = number;
export type Summary5 = string;
export type Id36 = string;
export type Seq36 = number;
export type MissionId36 = string | null;
export type ThreadId36 = string | null;
export type CheckpointId37 = string | null;
export type Ts36 = number;
export type AgentId48 = string | null;
export type Node40 = string | null;
export type Type36 = "memory.stored";
export type Collection = string;
export type DocId = string;
export type Title1 = string;
export type Id37 = string;
export type Seq37 = number;
export type MissionId37 = string | null;
export type ThreadId37 = string | null;
export type CheckpointId38 = string | null;
export type Ts37 = number;
export type AgentId49 = string | null;
export type Node41 = string | null;
export type Type37 = "memory.recalled";
export type Collection1 = string;
export type Query = string;
export type Hits = {
  [k: string]: unknown;
}[];
export type Id38 = string;
export type Seq38 = number;
export type MissionId38 = string | null;
export type ThreadId38 = string | null;
export type CheckpointId39 = string | null;
export type Ts38 = number;
export type AgentId50 = string | null;
export type Node42 = string | null;
export type Type38 = "risk.scored";
export type Level = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Score1 = number;
export type Route = string;
export type Id39 = string;
export type Seq39 = number;
export type MissionId39 = string | null;
export type ThreadId39 = string | null;
export type CheckpointId40 = string | null;
export type Ts39 = number;
export type AgentId51 = string | null;
export type Node43 = string | null;
export type Type39 = "guardrail.triggered";
export type Kind = "injection" | "pii" | "policy" | "allowlist" | "path_jail";
export type Detail1 = string;
export type Action = "redacted" | "blocked" | "flagged";
export type Id40 = string;
export type Seq40 = number;
export type MissionId40 = string | null;
export type ThreadId40 = string | null;
export type CheckpointId41 = string | null;
export type Ts40 = number;
export type AgentId52 = string | null;
export type Node44 = string | null;
export type Type40 = "interrupt.raised";
export type Kind1 = "approve_action" | "approve_team" | "edit_plan" | "answer_question";
export type ApprovalId = string;
export type Summary6 = string;
export type RiskLevel = string | null;
export type Id41 = string;
export type Seq41 = number;
export type MissionId41 = string | null;
export type ThreadId41 = string | null;
export type CheckpointId42 = string | null;
export type Ts41 = number;
export type AgentId53 = string | null;
export type Node45 = string | null;
export type Type41 = "interrupt.resolved";
export type ApprovalId1 = string;
export type Decision = "approve" | "reject" | "edit" | "respond";
export type By = string;
export type Channel1 = "ui" | "email" | "api" | "auto";
export type Id42 = string;
export type Seq42 = number;
export type MissionId42 = string | null;
export type ThreadId42 = string | null;
export type CheckpointId43 = string | null;
export type Ts42 = number;
export type AgentId54 = string | null;
export type Node46 = string | null;
export type Type42 = "email.sent";
export type To = string;
export type Subject = string;
export type MessageId = string;
export type Status2 = "sent" | "outbox";
export type Id43 = string;
export type Seq43 = number;
export type MissionId43 = string | null;
export type ThreadId43 = string | null;
export type CheckpointId44 = string | null;
export type Ts43 = number;
export type AgentId55 = string | null;
export type Node47 = string | null;
export type Type43 = "timetravel.fork";
export type FromCheckpoint = string;
export type NewCheckpoint = string;
export type PatchKeys = string[];
export type BranchId = string;
export type Id44 = string;
export type Seq44 = number;
export type MissionId44 = string | null;
export type ThreadId44 = string | null;
export type CheckpointId45 = string | null;
export type Ts44 = number;
export type AgentId56 = string | null;
export type Node48 = string | null;
export type Type44 = "governor.metrics";
export type RamTotalGb = number;
export type RamAvailableGb = number;
export type RamPercent = number;
export type Pressure = "normal" | "elevated" | "critical";
export type Limit = number;
export type ConfiguredLimit = number;
export type InFlight = number;
export type QueueDepth = number;
export type TokensPerSec1 = number;
export type LoadedModels = {
  [k: string]: unknown;
}[];
export type Id45 = string;
export type Seq45 = number;
export type MissionId45 = string | null;
export type ThreadId45 = string | null;
export type CheckpointId46 = string | null;
export type Ts45 = number;
export type AgentId57 = string | null;
export type Node49 = string | null;
export type Type45 = "incident.detected";
export type IncidentId = string;
export type Service = string;
export type Signal = string;
export type Detail2 = string;
export type Id46 = string;
export type Seq46 = number;
export type MissionId46 = string | null;
export type ThreadId46 = string | null;
export type CheckpointId47 = string | null;
export type Ts46 = number;
export type AgentId58 = string | null;
export type Node50 = string | null;
export type Type46 = "chaos.toggled";
export type Switch = string;
export type Enabled = boolean;
export type Id47 = string;
export type Seq47 = number;
export type MissionId47 = string | null;
export type ThreadId47 = string | null;
export type CheckpointId48 = string | null;
export type Ts47 = number;
export type AgentId59 = string | null;
export type Node51 = string | null;
export type Type47 = "service.health";
export type Service1 = string;
export type Status3 = "healthy" | "degraded" | "down";
export type ErrorRate = number;
export type LatencyMs = number | null;

export interface MissionCreatedEvent {
  id: Id;
  seq: Seq;
  mission_id?: MissionId;
  thread_id?: ThreadId;
  checkpoint_id?: CheckpointId;
  ts: Ts;
  agent_id?: AgentId;
  node?: Node;
  type: Type;
  payload: MissionCreated;
}
export interface MissionCreated {
  title: Title;
  playbook: Playbook;
  task: Task;
}
export interface MissionStartedEvent {
  id: Id1;
  seq: Seq1;
  mission_id?: MissionId1;
  thread_id?: ThreadId1;
  checkpoint_id?: CheckpointId1;
  ts: Ts1;
  agent_id?: AgentId1;
  node?: Node1;
  type: Type1;
  payload: MissionStarted;
}
export interface MissionStarted {
  resumed?: Resumed;
}
export interface MissionCompletedEvent {
  id: Id2;
  seq: Seq2;
  mission_id?: MissionId2;
  thread_id?: ThreadId2;
  checkpoint_id?: CheckpointId2;
  ts: Ts2;
  agent_id?: AgentId2;
  node?: Node2;
  type: Type2;
  payload: MissionCompleted;
}
export interface MissionCompleted {
  outcome: Outcome;
  summary: Summary;
}
export interface MissionFailedEvent {
  id: Id3;
  seq: Seq3;
  mission_id?: MissionId3;
  thread_id?: ThreadId3;
  checkpoint_id?: CheckpointId3;
  ts: Ts3;
  agent_id?: AgentId3;
  node?: Node3;
  type: Type3;
  payload: MissionFailed;
}
export interface MissionFailed {
  error: Error;
  node?: Node4;
}
export interface MissionCancelledEvent {
  id: Id4;
  seq: Seq4;
  mission_id?: MissionId4;
  thread_id?: ThreadId4;
  checkpoint_id?: CheckpointId4;
  ts: Ts4;
  agent_id?: AgentId4;
  node?: Node5;
  type: Type4;
  payload: MissionCancelled;
}
export interface MissionCancelled {
  reason: Reason;
}
export interface NodeEnteredEvent {
  id: Id5;
  seq: Seq5;
  mission_id?: MissionId5;
  thread_id?: ThreadId5;
  checkpoint_id?: CheckpointId5;
  ts: Ts5;
  agent_id?: AgentId5;
  node?: Node6;
  type: Type5;
  payload: NodeEntered;
}
export interface NodeEntered {
  node: Node7;
  step?: Step;
}
export interface NodeExitedEvent {
  id: Id6;
  seq: Seq6;
  mission_id?: MissionId6;
  thread_id?: ThreadId6;
  checkpoint_id?: CheckpointId6;
  ts: Ts6;
  agent_id?: AgentId6;
  node?: Node8;
  type: Type6;
  payload: NodeExited;
}
export interface NodeExited {
  node: Node9;
  duration_ms: DurationMs;
  status: Status;
  updated?: Updated;
}
export interface EdgeTakenEvent {
  id: Id7;
  seq: Seq7;
  mission_id?: MissionId7;
  thread_id?: ThreadId7;
  checkpoint_id?: CheckpointId7;
  ts: Ts7;
  agent_id?: AgentId7;
  node?: Node10;
  type: Type7;
  payload: EdgeTaken;
}
export interface EdgeTaken {
  source: Source;
  target: Target;
  label: Label;
}
export interface SendFanoutEvent {
  id: Id8;
  seq: Seq8;
  mission_id?: MissionId8;
  thread_id?: ThreadId8;
  checkpoint_id?: CheckpointId8;
  ts: Ts8;
  agent_id?: AgentId8;
  node?: Node11;
  type: Type8;
  payload: SendFanout;
}
export interface SendFanout {
  source: Source1;
  target: Target1;
  count: Count;
  items?: Items;
}
export interface SendFaninEvent {
  id: Id9;
  seq: Seq9;
  mission_id?: MissionId9;
  thread_id?: ThreadId9;
  checkpoint_id?: CheckpointId9;
  ts: Ts9;
  agent_id?: AgentId9;
  node?: Node12;
  type: Type9;
  payload: SendFanin;
}
export interface SendFanin {
  target: Target2;
  count: Count1;
}
export interface ReducerMergedEvent {
  id: Id10;
  seq: Seq10;
  mission_id?: MissionId10;
  thread_id?: ThreadId10;
  checkpoint_id?: CheckpointId10;
  ts: Ts10;
  agent_id?: AgentId10;
  node?: Node13;
  type: Type10;
  payload: ReducerMerged;
}
export interface ReducerMerged {
  channel: Channel;
  reducer: Reducer;
  added: Added;
  total: Total;
  detail?: Detail;
}
export interface HandoffEvent {
  id: Id11;
  seq: Seq11;
  mission_id?: MissionId11;
  thread_id?: ThreadId11;
  checkpoint_id?: CheckpointId11;
  ts: Ts11;
  agent_id?: AgentId11;
  node?: Node14;
  type: Type11;
  payload: Handoff;
}
export interface Handoff {
  source: Source2;
  target: Target3;
  reason: Reason1;
}
export interface CheckpointSavedEvent {
  id: Id12;
  seq: Seq12;
  mission_id?: MissionId12;
  thread_id?: ThreadId12;
  checkpoint_id?: CheckpointId12;
  ts: Ts12;
  agent_id?: AgentId12;
  node?: Node15;
  type: Type12;
  payload: CheckpointSaved;
}
export interface CheckpointSaved {
  checkpoint_id: CheckpointId13;
  step: Step1;
  next: Next;
}
export interface PlanCreatedEvent {
  id: Id13;
  seq: Seq13;
  mission_id?: MissionId13;
  thread_id?: ThreadId13;
  checkpoint_id?: CheckpointId14;
  ts: Ts13;
  agent_id?: AgentId13;
  node?: Node16;
  type: Type13;
  payload: PlanCreated;
}
export interface PlanCreated {
  steps: Steps;
  revision?: Revision;
  source: Source3;
}
export interface AgentAssignedEvent {
  id: Id14;
  seq: Seq14;
  mission_id?: MissionId14;
  thread_id?: ThreadId14;
  checkpoint_id?: CheckpointId15;
  ts: Ts14;
  agent_id?: AgentId14;
  node?: Node17;
  type: Type14;
  payload: AgentAssigned;
}
export interface AgentAssigned {
  agent_id: AgentId15;
  step_id?: StepId;
  task: Task1;
}
export interface AgentThinkingEvent {
  id: Id15;
  seq: Seq15;
  mission_id?: MissionId15;
  thread_id?: ThreadId15;
  checkpoint_id?: CheckpointId16;
  ts: Ts15;
  agent_id?: AgentId16;
  node?: Node18;
  type: Type15;
  payload: AgentThinking;
}
export interface AgentThinking {
  agent_id: AgentId17;
  text: Text;
  iteration?: Iteration;
}
export interface AgentTokenEvent {
  id: Id16;
  seq: Seq16;
  mission_id?: MissionId16;
  thread_id?: ThreadId16;
  checkpoint_id?: CheckpointId17;
  ts: Ts16;
  agent_id?: AgentId18;
  node?: Node19;
  type: Type16;
  payload: AgentToken;
}
export interface AgentToken {
  agent_id: AgentId19;
  text: Text1;
  purpose: Purpose;
}
export interface AgentActionEvent {
  id: Id17;
  seq: Seq17;
  mission_id?: MissionId17;
  thread_id?: ThreadId17;
  checkpoint_id?: CheckpointId18;
  ts: Ts17;
  agent_id?: AgentId20;
  node?: Node20;
  type: Type17;
  payload: AgentAction;
}
export interface AgentAction {
  agent_id: AgentId21;
  tool: Tool;
  args: Args;
  iteration?: Iteration1;
}
export interface Args {
  [k: string]: unknown;
}
export interface AgentObservationEvent {
  id: Id18;
  seq: Seq18;
  mission_id?: MissionId18;
  thread_id?: ThreadId18;
  checkpoint_id?: CheckpointId19;
  ts: Ts18;
  agent_id?: AgentId22;
  node?: Node21;
  type: Type18;
  payload: AgentObservation;
}
export interface AgentObservation {
  agent_id: AgentId23;
  tool: Tool1;
  summary: Summary1;
  ok?: Ok;
}
export interface AgentFinalEvent {
  id: Id19;
  seq: Seq19;
  mission_id?: MissionId19;
  thread_id?: ThreadId19;
  checkpoint_id?: CheckpointId20;
  ts: Ts19;
  agent_id?: AgentId24;
  node?: Node22;
  type: Type19;
  payload: AgentFinal;
}
export interface AgentFinal {
  agent_id: AgentId25;
  answer: Answer;
}
export interface AgentStatusEvent {
  id: Id20;
  seq: Seq20;
  mission_id?: MissionId20;
  thread_id?: ThreadId20;
  checkpoint_id?: CheckpointId21;
  ts: Ts20;
  agent_id?: AgentId26;
  node?: Node23;
  type: Type20;
  payload: AgentStatus;
}
/**
 * Coarse robot state for the UI state machine (idle, walking, celebrating...).
 */
export interface AgentStatus {
  agent_id: AgentId27;
  status: Status1;
}
export interface ToolCalledEvent {
  id: Id21;
  seq: Seq21;
  mission_id?: MissionId21;
  thread_id?: ThreadId21;
  checkpoint_id?: CheckpointId22;
  ts: Ts21;
  agent_id?: AgentId28;
  node?: Node24;
  type: Type21;
  payload: ToolCalled;
}
export interface ToolCalled {
  server: Server;
  tool: Tool2;
  call_id: CallId;
  args: Args1;
  agent_id?: AgentId29;
}
export interface Args1 {
  [k: string]: unknown;
}
export interface ToolResultEvent {
  id: Id22;
  seq: Seq22;
  mission_id?: MissionId22;
  thread_id?: ThreadId22;
  checkpoint_id?: CheckpointId23;
  ts: Ts22;
  agent_id?: AgentId30;
  node?: Node25;
  type: Type22;
  payload: ToolResult;
}
export interface ToolResult {
  server: Server1;
  tool: Tool3;
  call_id: CallId1;
  ok: Ok1;
  summary: Summary2;
  duration_ms: DurationMs1;
}
export interface CouncilProposalEvent {
  id: Id23;
  seq: Seq23;
  mission_id?: MissionId23;
  thread_id?: ThreadId23;
  checkpoint_id?: CheckpointId24;
  ts: Ts23;
  agent_id?: AgentId31;
  node?: Node26;
  type: Type23;
  payload: CouncilProposal;
}
export interface CouncilProposal {
  solver_id: SolverId;
  strategy: Strategy;
  summary: Summary3;
  label?: Label1;
}
export interface CouncilMaskedEvent {
  id: Id24;
  seq: Seq24;
  mission_id?: MissionId24;
  thread_id?: ThreadId24;
  checkpoint_id?: CheckpointId25;
  ts: Ts24;
  agent_id?: AgentId32;
  node?: Node27;
  type: Type24;
  payload: CouncilMasked;
}
export interface CouncilMasked {
  mapping_hidden?: MappingHidden;
  labels: Labels;
}
export interface CouncilReviewEvent {
  id: Id25;
  seq: Seq25;
  mission_id?: MissionId25;
  thread_id?: ThreadId25;
  checkpoint_id?: CheckpointId26;
  ts: Ts25;
  agent_id?: AgentId33;
  node?: Node28;
  type: Type25;
  payload: CouncilReview;
}
export interface CouncilReview {
  reviewer: Reviewer;
  target_label: TargetLabel;
  score: Score;
  scores: Scores;
  reason: Reason2;
}
export interface Scores {
  [k: string]: number;
}
export interface CouncilRoundEvent {
  id: Id26;
  seq: Seq26;
  mission_id?: MissionId26;
  thread_id?: ThreadId26;
  checkpoint_id?: CheckpointId27;
  ts: Ts26;
  agent_id?: AgentId34;
  node?: Node29;
  type: Type26;
  payload: CouncilRound;
}
export interface CouncilRound {
  round: Round;
  divergence: Divergence;
  converged: Converged;
}
export interface CouncilVerdictEvent {
  id: Id27;
  seq: Seq27;
  mission_id?: MissionId27;
  thread_id?: ThreadId27;
  checkpoint_id?: CheckpointId28;
  ts: Ts27;
  agent_id?: AgentId35;
  node?: Node30;
  type: Type27;
  payload: CouncilVerdict;
}
export interface CouncilVerdict {
  winner: Winner;
  winner_label: WinnerLabel;
  runner_up: RunnerUp;
  confidence: Confidence;
  dissent: Dissent;
  final_scores: FinalScores;
  escalate: Escalate;
}
export interface FinalScores {
  [k: string]: number;
}
export interface SandboxTestResultEvent {
  id: Id28;
  seq: Seq28;
  mission_id?: MissionId28;
  thread_id?: ThreadId28;
  checkpoint_id?: CheckpointId29;
  ts: Ts28;
  agent_id?: AgentId36;
  node?: Node31;
  type: Type28;
  payload: SandboxTestResult;
}
export interface SandboxTestResult {
  target: Target4;
  passed: Passed;
  failed: Failed;
  errors: Errors;
  ok: Ok2;
  duration_ms: DurationMs2;
  backend: Backend;
  summary?: Summary4;
}
export interface RetryEvent {
  id: Id29;
  seq: Seq29;
  mission_id?: MissionId29;
  thread_id?: ThreadId29;
  checkpoint_id?: CheckpointId30;
  ts: Ts29;
  agent_id?: AgentId37;
  node?: Node32;
  type: Type29;
  payload: Retry;
}
export interface Retry {
  layer: Layer;
  key: Key;
  attempt: Attempt;
  max_attempts: MaxAttempts;
  reason: Reason3;
  agent_id?: AgentId38;
}
export interface CircuitStateEvent {
  id: Id30;
  seq: Seq30;
  mission_id?: MissionId30;
  thread_id?: ThreadId30;
  checkpoint_id?: CheckpointId31;
  ts: Ts30;
  agent_id?: AgentId39;
  node?: Node33;
  type: Type30;
  payload: CircuitState;
}
export interface CircuitState {
  key: Key1;
  state: State;
  failures: Failures;
}
export interface LlmRoutedEvent {
  id: Id31;
  seq: Seq31;
  mission_id?: MissionId31;
  thread_id?: ThreadId31;
  checkpoint_id?: CheckpointId32;
  ts: Ts31;
  agent_id?: AgentId40;
  node?: Node34;
  type: Type31;
  payload: LlmRouted;
}
export interface LlmRouted {
  purpose: Purpose1;
  role: Role;
  model: Model;
  reason: Reason4;
}
export interface LlmCallEvent {
  id: Id32;
  seq: Seq32;
  mission_id?: MissionId32;
  thread_id?: ThreadId32;
  checkpoint_id?: CheckpointId33;
  ts: Ts32;
  agent_id?: AgentId41;
  node?: Node35;
  type: Type32;
  payload: LlmCall;
}
export interface LlmCall {
  model: Model1;
  purpose: Purpose2;
  agent_id?: AgentId42;
  prompt_tokens: PromptTokens;
  completion_tokens: CompletionTokens;
  estimated_prompt_tokens: EstimatedPromptTokens;
  duration_ms: DurationMs3;
  tokens_per_sec: TokensPerSec;
}
export interface DeadLetterEvent {
  id: Id33;
  seq: Seq33;
  mission_id?: MissionId33;
  thread_id?: ThreadId33;
  checkpoint_id?: CheckpointId34;
  ts: Ts33;
  agent_id?: AgentId43;
  node?: Node36;
  type: Type33;
  payload: DeadLetter;
}
export interface DeadLetter {
  node: Node37;
  error: Error1;
  attempts: Attempts;
}
export interface MemoryPrunedEvent {
  id: Id34;
  seq: Seq34;
  mission_id?: MissionId34;
  thread_id?: ThreadId34;
  checkpoint_id?: CheckpointId35;
  ts: Ts34;
  agent_id?: AgentId44;
  node?: Node38;
  type: Type34;
  payload: MemoryPruned;
}
export interface MemoryPruned {
  agent_id: AgentId45;
  strategy: Strategy1;
  before_tokens: BeforeTokens;
  after_tokens: AfterTokens;
  dropped_messages: DroppedMessages;
  budget: Budget;
}
export interface MemorySummarisedEvent {
  id: Id35;
  seq: Seq35;
  mission_id?: MissionId35;
  thread_id?: ThreadId35;
  checkpoint_id?: CheckpointId36;
  ts: Ts35;
  agent_id?: AgentId46;
  node?: Node39;
  type: Type35;
  payload: MemorySummarised;
}
export interface MemorySummarised {
  agent_id: AgentId47;
  before_tokens: BeforeTokens1;
  after_tokens: AfterTokens1;
  summary: Summary5;
}
export interface MemoryStoredEvent {
  id: Id36;
  seq: Seq36;
  mission_id?: MissionId36;
  thread_id?: ThreadId36;
  checkpoint_id?: CheckpointId37;
  ts: Ts36;
  agent_id?: AgentId48;
  node?: Node40;
  type: Type36;
  payload: MemoryStored;
}
export interface MemoryStored {
  collection: Collection;
  doc_id: DocId;
  title: Title1;
}
export interface MemoryRecalledEvent {
  id: Id37;
  seq: Seq37;
  mission_id?: MissionId37;
  thread_id?: ThreadId37;
  checkpoint_id?: CheckpointId38;
  ts: Ts37;
  agent_id?: AgentId49;
  node?: Node41;
  type: Type37;
  payload: MemoryRecalled;
}
export interface MemoryRecalled {
  collection: Collection1;
  query: Query;
  hits: Hits;
}
export interface RiskScoredEvent {
  id: Id38;
  seq: Seq38;
  mission_id?: MissionId38;
  thread_id?: ThreadId38;
  checkpoint_id?: CheckpointId39;
  ts: Ts38;
  agent_id?: AgentId50;
  node?: Node42;
  type: Type38;
  payload: RiskScored;
}
export interface RiskScored {
  level: Level;
  score: Score1;
  factors: Factors;
  route: Route;
}
export interface Factors {
  [k: string]: number;
}
export interface GuardrailTriggeredEvent {
  id: Id39;
  seq: Seq39;
  mission_id?: MissionId39;
  thread_id?: ThreadId39;
  checkpoint_id?: CheckpointId40;
  ts: Ts39;
  agent_id?: AgentId51;
  node?: Node43;
  type: Type39;
  payload: GuardrailTriggered;
}
export interface GuardrailTriggered {
  kind: Kind;
  detail: Detail1;
  action: Action;
}
export interface InterruptRaisedEvent {
  id: Id40;
  seq: Seq40;
  mission_id?: MissionId40;
  thread_id?: ThreadId40;
  checkpoint_id?: CheckpointId41;
  ts: Ts40;
  agent_id?: AgentId52;
  node?: Node44;
  type: Type40;
  payload: InterruptRaised;
}
export interface InterruptRaised {
  kind: Kind1;
  approval_id: ApprovalId;
  summary: Summary6;
  risk_level?: RiskLevel;
}
export interface InterruptResolvedEvent {
  id: Id41;
  seq: Seq41;
  mission_id?: MissionId41;
  thread_id?: ThreadId41;
  checkpoint_id?: CheckpointId42;
  ts: Ts41;
  agent_id?: AgentId53;
  node?: Node45;
  type: Type41;
  payload: InterruptResolved;
}
export interface InterruptResolved {
  approval_id: ApprovalId1;
  decision: Decision;
  by: By;
  channel: Channel1;
}
export interface EmailSentEvent {
  id: Id42;
  seq: Seq42;
  mission_id?: MissionId42;
  thread_id?: ThreadId42;
  checkpoint_id?: CheckpointId43;
  ts: Ts42;
  agent_id?: AgentId54;
  node?: Node46;
  type: Type42;
  payload: EmailSent;
}
export interface EmailSent {
  to: To;
  subject: Subject;
  message_id: MessageId;
  status: Status2;
}
export interface TimetravelForkEvent {
  id: Id43;
  seq: Seq43;
  mission_id?: MissionId43;
  thread_id?: ThreadId43;
  checkpoint_id?: CheckpointId44;
  ts: Ts43;
  agent_id?: AgentId55;
  node?: Node47;
  type: Type43;
  payload: TimetravelFork;
}
export interface TimetravelFork {
  from_checkpoint: FromCheckpoint;
  new_checkpoint: NewCheckpoint;
  patch_keys: PatchKeys;
  branch_id: BranchId;
}
export interface GovernorMetricsEvent {
  id: Id44;
  seq: Seq44;
  mission_id?: MissionId44;
  thread_id?: ThreadId44;
  checkpoint_id?: CheckpointId45;
  ts: Ts44;
  agent_id?: AgentId56;
  node?: Node48;
  type: Type44;
  payload: GovernorMetrics;
}
export interface GovernorMetrics {
  ram_total_gb: RamTotalGb;
  ram_available_gb: RamAvailableGb;
  ram_percent: RamPercent;
  pressure: Pressure;
  limit: Limit;
  configured_limit: ConfiguredLimit;
  in_flight: InFlight;
  queue_depth: QueueDepth;
  tokens_per_sec: TokensPerSec1;
  loaded_models: LoadedModels;
}
export interface IncidentDetectedEvent {
  id: Id45;
  seq: Seq45;
  mission_id?: MissionId45;
  thread_id?: ThreadId45;
  checkpoint_id?: CheckpointId46;
  ts: Ts45;
  agent_id?: AgentId57;
  node?: Node49;
  type: Type45;
  payload: IncidentDetected;
}
export interface IncidentDetected {
  incident_id: IncidentId;
  service: Service;
  signal: Signal;
  detail: Detail2;
}
export interface ChaosToggledEvent {
  id: Id46;
  seq: Seq46;
  mission_id?: MissionId46;
  thread_id?: ThreadId46;
  checkpoint_id?: CheckpointId47;
  ts: Ts46;
  agent_id?: AgentId58;
  node?: Node50;
  type: Type46;
  payload: ChaosToggled;
}
export interface ChaosToggled {
  switch: Switch;
  enabled: Enabled;
}
export interface ServiceHealthEvent {
  id: Id47;
  seq: Seq47;
  mission_id?: MissionId47;
  thread_id?: ThreadId47;
  checkpoint_id?: CheckpointId48;
  ts: Ts47;
  agent_id?: AgentId59;
  node?: Node51;
  type: Type47;
  payload: ServiceHealth;
}
export interface ServiceHealth {
  service: Service1;
  status: Status3;
  error_rate: ErrorRate;
  latency_ms: LatencyMs;
}
