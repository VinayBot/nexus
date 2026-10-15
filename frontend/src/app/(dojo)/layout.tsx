import { LiveBridge } from "@/components/layout/LiveBridge";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { SkyBackdrop } from "@/components/scenery/SkyBackdrop";

/** Shell for every in-app screen: sky behind, nav on the left, top bar, scrolling content. */
export default function DojoLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh">
      <SkyBackdrop />
      <LiveBridge />
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main" className="min-h-0 flex-1 overflow-y-auto p-3">
          {children}
        </main>
      </div>
    </div>
  );
}
