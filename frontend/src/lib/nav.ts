import {
  Activity,
  BookOpenCheck,
  Bot,
  Brain,
  Cpu,
  FlaskConical,
  GitFork,
  LayoutDashboard,
  Network,
  Settings,
  Shield,
  Stamp,
  Swords,
  Bell,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  /** Short Japanese-flavoured subtitle shown under the label. */
  kanji: string;
  icon: LucideIcon;
  /** Routes that need a mission id resolve it from the active mission. */
  needsMission?: boolean;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    title: "Missions",
    items: [
      { href: "/dojo", label: "Mission Control", kanji: "道場", icon: LayoutDashboard },
      { href: "/graph", label: "Live Graph", kanji: "流れ", icon: Workflow, needsMission: true },
      { href: "/arena", label: "Council Arena", kanji: "闘技", icon: Swords, needsMission: true },
      { href: "/approvals", label: "Shogun's Seal", kanji: "印", icon: Stamp },
      { href: "/timetravel", label: "Scroll of Time", kanji: "時", icon: GitFork, needsMission: true },
    ],
  },
  {
    title: "Clan",
    items: [
      { href: "/memory", label: "Memory Palace", kanji: "記憶", icon: Brain },
      { href: "/barracks", label: "Barracks", kanji: "兵舎", icon: Bot },
      { href: "/armory", label: "Armory", kanji: "武器", icon: Shield },
      { href: "/shrine", label: "Chaos Shrine", kanji: "神社", icon: Bell },
    ],
  },
  {
    title: "Insight",
    items: [
      { href: "/observatory", label: "Observatory", kanji: "観測", icon: Activity },
      { href: "/evals", label: "Proving Grounds", kanji: "試練", icon: FlaskConical },
      { href: "/architecture", label: "Architecture", kanji: "設計", icon: Network },
      { href: "/curriculum", label: "Curriculum Map", kanji: "学び", icon: BookOpenCheck },
      { href: "/under-the-hood", label: "Under the Hood", kanji: "内部", icon: Cpu },
      { href: "/settings", label: "Settings", kanji: "設定", icon: Settings },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);
