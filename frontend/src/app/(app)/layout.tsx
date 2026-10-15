import { Nova } from "@/components/guide/Nova";
import { TourOverlay } from "@/components/guide/TourOverlay";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { LiveBridge } from "@/components/layout/LiveBridge";
import { Toasts } from "@/components/layout/Toasts";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { SkyBackdrop } from "@/components/scenery/SkyBackdrop";

/** Shell for every in-app screen: sky behind, nav on the left, top bar, scrolling content. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh">
      <SkyBackdrop />
      <LiveBridge />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[80] focus:rounded focus:bg-black focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main" className="min-h-0 flex-1 overflow-y-auto p-3">
          {children}
        </main>
      </div>
      <Toasts />
      <Nova />
      <TourOverlay />
      <CommandPalette />
    </div>
  );
}
