import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { MeetingStatus } from '../api/client';

function statusBadge(status: MeetingStatus) {
  const colors: Record<MeetingStatus, string> = {
    recording: 'bg-slate-200 text-slate-700',
    transcribing: 'bg-amber-100 text-amber-800',
    formatting: 'bg-blue-100 text-blue-800',
    formatted: 'bg-emerald-100 text-emerald-800',
    error: 'bg-red-100 text-red-800',
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${colors[status]}`}
    >
      {status}
    </span>
  );
}

export function Dashboard() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [newProjectName, setNewProjectName] = useState('');
  const [showAddProject, setShowAddProject] = useState(false);

  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: api.projects.list,
  });

  const currentProjectId = projectId ? parseInt(projectId, 10) : null;
  const { data: meetings, isLoading: meetingsLoading } = useQuery({
    queryKey: ['meetings', currentProjectId],
    queryFn: () => api.meetings.list(currentProjectId!),
    enabled: currentProjectId != null,
  });

  const createProjectMutation = useMutation({
    mutationFn: (name: string) => api.projects.create(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setNewProjectName('');
      setShowAddProject(false);
    },
  });

  // No project selected: show project directory
  if (!projectId) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold text-slate-900">Projects</h1>
        <p className="text-slate-500">Select a project or create one to add meetings.</p>

        {projectsLoading ? (
          <div className="flex justify-center py-12 text-slate-500">Loading…</div>
        ) : (
          <div className="space-y-2">
            {projects?.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm hover:bg-slate-50"
              >
                <span className="text-lg text-slate-400">📁</span>
                <span className="font-medium text-slate-900">{p.name}</span>
                <span className="text-sm text-slate-400">
                  {new Date(p.created_at).toLocaleDateString()}
                </span>
              </Link>
            ))}
            {showAddProject ? (
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="Project name"
                  className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
                  autoFocus
                />
                <button
                  onClick={() => createProjectMutation.mutate(newProjectName || 'Untitled Project')}
                  disabled={createProjectMutation.isPending}
                  className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  Add
                </button>
                <button
                  onClick={() => {
                    setShowAddProject(false);
                    setNewProjectName('');
                  }}
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowAddProject(true)}
                className="flex items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-3 text-slate-600 hover:bg-slate-50"
              >
                <span className="text-lg">+</span>
                New project
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  // Project selected: show meetings in this project (directory of meetings)
  const project = projects?.find((p) => p.id === currentProjectId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">
            ← Projects
          </Link>
          <h1 className="text-2xl font-semibold text-slate-900">
            {project?.name ?? 'Project'}
          </h1>
        </div>
        <Link
          to="/record"
          state={currentProjectId != null ? { projectId: currentProjectId } : undefined}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          New meeting
        </Link>
      </div>

      <h2 className="text-lg font-medium text-slate-700">Meetings</h2>
      {meetingsLoading ? (
        <div className="flex justify-center py-12 text-slate-500">Loading…</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Meeting
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!meetings?.length ? (
                <tr>
                  <td colSpan={3} className="px-6 py-12 text-center text-slate-500">
                    No meetings yet. Create one from &quot;New meeting&quot; and select this project.
                  </td>
                </tr>
              ) : (
                meetings.map((m) => (
                  <tr
                    key={m.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/meetings/${m.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        navigate(`/meetings/${m.id}`);
                      }
                    }}
                    className="cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                  >
                    <td className="px-6 py-4 font-medium text-slate-900">{m.title}</td>
                    <td className="px-6 py-4 text-slate-500">
                      {new Date(m.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4">{statusBadge(m.status)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
