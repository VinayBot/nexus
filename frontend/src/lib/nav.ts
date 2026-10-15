import {
  Activity,
  Bot,
  Brain,
  GitFork,
  LayoutDashboard,
  Network,
  Settings,
  Shield,
  Stamp,
  Swords,
  Zap,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Routes that need a mission id resolve it from the active mission. */
  needsMission?: boolean;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

/** Main screens — always visible. */
export const NAV: NavGroup[] = [
  {
    title: "Command",
    items: [
      { href: "/missions", label: "Mission Control", icon: LayoutDashboard },
      { href: "/graph", label: "Live Graph", icon: Workflow, needsMission: true },
      { href: "/arena", label: "Arena", icon: Swords, needsMission: true },
      { href: "/approvals", label: "Approvals", icon: Stamp },
      { href: "/timetravel", label: "Time Travel", icon: GitFork, needsMission: true },
      { href: "/chaos", label: "Chaos Lab", icon: Zap },
      { href: "/agents", label: "Agents", icon: Bot },
      { href: "/insights", label: "Insights", icon: Activity },
    ],
  },
  {
    title: "More",
    items: [
      { href: "/memory", label: "Memory", icon: Brain },
      { href: "/tools", label: "Tools", icon: Shield },
      { href: "/learn", label: "How it Works", icon: Network },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);
