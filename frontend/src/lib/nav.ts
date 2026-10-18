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

/** Main screens first; specialist views (graph, arena, time travel…) under "Advanced". */
export const NAV: NavGroup[] = [
  {
    title: "Main",
    items: [
      { href: "/missions", label: "Missions", icon: LayoutDashboard },
      { href: "/approvals", label: "Approvals", icon: Stamp },
      { href: "/agents", label: "Agents", icon: Bot },
      { href: "/insights", label: "Insights", icon: Activity },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
  {
    title: "Advanced",
    items: [
      { href: "/graph", label: "Live Graph", icon: Workflow, needsMission: true },
      { href: "/arena", label: "Arena", icon: Swords, needsMission: true },
      { href: "/timetravel", label: "Time Travel", icon: GitFork, needsMission: true },
      { href: "/chaos", label: "Chaos Lab", icon: Zap },
      { href: "/memory", label: "Memory", icon: Brain },
      { href: "/tools", label: "Tools", icon: Shield },
      { href: "/learn", label: "How it Works", icon: Network },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);
