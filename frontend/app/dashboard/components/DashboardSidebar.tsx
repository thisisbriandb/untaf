"use client";

import { LayoutDashboard, Target, Briefcase, MessageSquare, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

export type TabType = "alice" | "mission" | "candidatures" | "messages" | "parametres";

interface DashboardSidebarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  applicationsCount: number;
  userName: string;
  userEmail: string;
  onLogout: () => void;
}

export function DashboardSidebar({
  activeTab,
  onSelectTab,
  userName,
}: DashboardSidebarProps) {
  const initials = userName
    ? userName
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "BR";

  const navItems = [
    { id: "alice", label: "Dashboard", icon: LayoutDashboard },
    { id: "mission", label: "Mission", icon: Target },
    { id: "candidatures", label: "Candidatures", icon: Briefcase },
    { id: "messages", label: "Messages", icon: MessageSquare },
    { id: "parametres", label: "Paramètres", icon: Settings },
  ];

  return (
    <aside className="fixed top-0 left-0 h-screen w-14 max-w-[56px] bg-[#FAFAF8]/95 border-r border-[#1A1918]/6 flex flex-col items-center justify-between py-6 z-50 select-none">
      {/* Top Discreet Navigation */}
      <div className="flex flex-col items-center gap-6 w-full px-2">
        <nav className="flex flex-col items-center gap-3 w-full">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id as TabType)}
                title={item.label}
                className={cn(
                  "p-2.5 rounded-xl transition-all cursor-pointer relative flex items-center justify-center",
                  isActive
                    ? "bg-[#1A1918]/8 text-[#1A1918]"
                    : "text-[#1A1918]/55 hover:text-[#1A1918] hover:bg-[#1A1918]/4"
                )}
              >
                <Icon className="w-4 h-4 stroke-[1.3]" />
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom User Avatar Badge (Ultra Minimalist) */}
      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={() => onSelectTab("parametres")}
          title={userName}
          className="w-7 h-7 rounded-full bg-[#1A1918]/8 text-[#1A1918]/80 flex items-center justify-center text-[11px] font-medium cursor-pointer hover:bg-[#1A1918]/15 transition-colors"
        >
          {initials}
        </button>
      </div>
    </aside>
  );
}
