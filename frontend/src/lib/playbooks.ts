import { Bot, Code2, FileText, Globe, MessageCircleQuestion, Sparkles, Wrench, type LucideIcon } from "lucide-react";

export interface MissionType {
  /** Playbook id; "" lets the Commander route it. */
  id: string;
  label: string;
  hint: string;
  example: string;
  icon: LucideIcon;
}

/** The mission types shown in the composer, in plain English. */
export const MISSION_TYPES: MissionType[] = [
  {
    id: "",
    label: "Auto",
    hint: "The Commander reads your request and picks the right team.",
    example: "Write a blog post about how AI agents use tools, as an HTML page.",
    icon: Sparkles,
  },
  {
    id: "web_builder",
    label: "Web page",
    hint: "Writes a blog post, article or landing page and publishes it as a styled HTML page with a link.",
    example: "Build an HTML page with a blog post about the future of AI in healthcare.",
    icon: Globe,
  },
  {
    id: "council_qa",
    label: "Question",
    hint: "Three agents answer independently, review each other anonymously, and a judge picks the best.",
    example: "What is the difference between ReAct and Plan-and-Execute agents?",
    icon: MessageCircleQuestion,
  },
  {
    id: "self_healing",
    label: "Fix service",
    hint: "Finds the bug in the demo shop, tests three fixes, asks you, applies the winner and verifies it.",
    example: "The demo-service is unhealthy. Investigate, fix and verify it.",
    icon: Wrench,
  },
  {
    id: "project_builder",
    label: "Build API",
    hint: "Builds a small tested FastAPI service or CLI tool (8 files or fewer) and packages it as a zip.",
    example: "Build a small FastAPI API to manage books (title, author, year) with tests.",
    icon: Code2,
  },
  {
    id: "ticket_solver",
    label: "Ticket",
    hint: "Reads a ticket, writes the fix with tests, and comments on the ticket after your approval.",
    example: "Solve ticket T-101",
    icon: FileText,
  },
  {
    id: "dynamic",
    label: "Custom team",
    hint: "The Commander designs a team for any task and asks you to approve it before work starts.",
    example: "Review the demo-service code for risky error handling and summarise the top 3 issues.",
    icon: Bot,
  },
];

const NAMES: Record<string, string> = {
  web_builder: "Web page",
  council_qa: "Question",
  self_healing: "Fix service",
  project_builder: "Build API",
  ticket_solver: "Ticket",
  dynamic: "Custom team",
};

export const playbookName = (id: string | null | undefined) => (id ? (NAMES[id] ?? id.replace(/_/g, " ")) : "Auto");
