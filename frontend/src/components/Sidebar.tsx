import React from 'react';
import {
  LayoutDashboard,
  Network,
  PlaySquare,
  Cpu,
  BookOpen,
  HelpCircle,
  Tv,
} from 'lucide-react';
import { ActiveView } from '../types';
import { EXAMPLE_MACHINES } from '../utils/examples';

interface SidebarProps {
  currentView: ActiveView;
  onSelectView: (view: ActiveView) => void;
  apiStatus: string;
  onReplayBoot: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  apiStatus,
  onReplayBoot,
}) => {
  const navItems = [
    { id: 'dashboard' as ActiveView, label: 'Overview', icon: LayoutDashboard, badge: null },
    { id: 'workspace' as ActiveView, label: 'Machine Editor', icon: Network, badge: null },
    { id: 'simulation' as ActiveView, label: 'Tape Playback', icon: PlaySquare, badge: null },
    { id: 'predictor' as ActiveView, label: 'ML Predictor', icon: Cpu, badge: 'Phase 2' },
    { id: 'examples' as ActiveView, label: 'Examples', icon: BookOpen, badge: String(EXAMPLE_MACHINES.length) },
    { id: 'help' as ActiveView, label: 'TOC Reference', icon: HelpCircle, badge: null },
  ];

  return (
    <aside className="app-sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-logo-icon">
          <span className="logo-symbol">δ</span>
        </div>
        <div className="brand-text">
          <div className="brand-title">Turing Machine</div>
          <div className="brand-subtitle">Simulator & Predictor</div>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="sidebar-nav">
        <div className="nav-section-label">WORKSPACE</div>
        <ul className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <li key={item.id}>
                <button
                  className={`nav-btn ${isActive ? 'active' : ''}`}
                  onClick={() => onSelectView(item.id)}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon size={18} className="nav-icon" />
                  <span className="nav-label">{item.label}</span>
                  {item.badge && (
                    <span className={`nav-badge ${item.badge === 'Phase 2' ? 'badge-phase' : 'badge-count'}`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* System & Health Status in Footer */}
      <div className="sidebar-footer">
        <div className="status-pill">
          <span
            className={`status-dot ${
              apiStatus === 'ok' ? 'status-online' : apiStatus === 'offline' ? 'status-offline' : 'status-pending'
            }`}
          />
          <span className="status-label">
            {apiStatus === 'ok' ? 'Backend Ready' : apiStatus === 'offline' ? 'Local Standalone' : 'Connecting...'}
          </span>
        </div>

        <button
          className="sidebar-retro-action"
          onClick={onReplayBoot}
          title="Replay retro boot intro screen"
        >
          <Tv size={14} />
          <span>Replay Intro</span>
        </button>

        <div className="sidebar-version-tag">
          TOC Simulator v1.0.0
        </div>
      </div>
    </aside>
  );
};

