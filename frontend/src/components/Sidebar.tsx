import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const iconClass = 'w-6 h-6 shrink-0';
const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center justify-center w-12 h-12 rounded-lg transition-colors ${
    isActive ? 'bg-indigo-100 text-indigo-600' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
  }`;

function IconProjects() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
  );
}
function IconVoice() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  );
}
function IconTemplates() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}
function IconNewMeeting() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}
function IconSettings() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}
function IconAbout() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
function IconUsers() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
  );
}
function IconLogout() {
  return (
    <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  );
}

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 z-10 flex h-screen w-14 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-14 shrink-0 items-center justify-center border-b border-slate-200">
        <span className="text-xs font-semibold text-slate-500">MLM</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-2">
        <NavLink to="/" end className={linkClass} title="Projects">
          <IconProjects />
        </NavLink>
        <NavLink to="/voice-samples" className={linkClass} title="Voice samples">
          <IconVoice />
        </NavLink>
        <NavLink to="/templates" className={linkClass} title="Templates">
          <IconTemplates />
        </NavLink>
        <NavLink to="/record" className={linkClass} title="New meeting">
          <IconNewMeeting />
        </NavLink>
        <div className="flex-1" />
        {user?.id === 1 && (
          <NavLink to="/users" className={linkClass} title="Users">
            <IconUsers />
          </NavLink>
        )}
        <NavLink to="/about" className={linkClass} title="About">
          <IconAbout />
        </NavLink>
      </nav>
      <div className="border-t border-slate-200 p-2">
        <div className="flex flex-col items-center gap-1">
          <span className="w-full truncate text-center text-xs text-slate-500" title={user?.username}>
            {user?.username}
          </span>
          <button
            type="button"
            onClick={logout}
            title="Log out"
            className="flex items-center justify-center w-12 h-12 rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            <IconLogout />
          </button>
        </div>
      </div>
    </aside>
  );
}
