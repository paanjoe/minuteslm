import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Template } from '../api/client';

export function Templates() {
  const queryClient = useQueryClient();
  const templateFileInput = useRef<HTMLInputElement>(null);
  const [projectFilter, setProjectFilter] = useState<number | ''>('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formName, setFormName] = useState('');
  const [formProjectId, setFormProjectId] = useState<number | ''>('');
  const [formFormatSpecMarkdown, setFormFormatSpecMarkdown] = useState('');

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: api.projects.list,
  });

  const { data: templates, isLoading } = useQuery({
    queryKey: ['templates', projectFilter || undefined],
    queryFn: () =>
      api.templates.list(projectFilter === '' ? undefined : projectFilter),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.templates.create({
        name: formName || 'Untitled Template',
        project_id: formProjectId === '' ? null : formProjectId,
        format_spec_markdown: formFormatSpecMarkdown.trim() || null,
      }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      setShowForm(false);
      setFormName('');
      setFormProjectId('');
      setFormFormatSpecMarkdown('');
      if (pendingFile && created?.id) {
        uploadMutation.mutate({ templateId: created.id, file: pendingFile });
        setPendingFile(null);
      }
    },
  });

  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const uploadMutation = useMutation({
    mutationFn: ({ templateId, file }: { templateId: number; file: File }) =>
      api.templates.uploadFile(templateId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      setPendingFile(null);
      if (templateFileInput.current) templateFileInput.current.value = '';
    },
  });

  const updateMutation = useMutation({
    mutationFn: (id: number) =>
      api.templates.update(id, {
        name: formName,
        project_id: formProjectId === '' ? null : formProjectId,
        format_spec_markdown: formFormatSpecMarkdown.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      setEditingId(null);
      setFormName('');
      setFormProjectId('');
      setFormFormatSpecMarkdown('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.templates.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['templates'] }),
  });

  const startEdit = (t: Template) => {
    api.templates.get(t.id).then((full) => {
      setEditingId(full.id);
      setFormName(full.name);
      setFormProjectId(full.project_id ?? '');
      setFormFormatSpecMarkdown(full.format_spec_markdown ?? '');
      setPendingFile(null);
      if (templateFileInput.current) templateFileInput.current.value = '';
    });
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormName('');
    setFormProjectId('');
    setFormFormatSpecMarkdown('');
    setPendingFile(null);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">
        Minutes templates
      </h1>
      <p className="text-slate-600">
        Organize format templates per client/project. Upload a Word or text
        template; the LLM will use it to structure minutes. Tie a template to a
        project or assign per meeting.
      </p>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Filter by project:
          <select
            value={projectFilter}
            onChange={(e) =>
              setProjectFilter(e.target.value === '' ? '' : Number(e.target.value))
            }
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">All templates</option>
            {projects?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {!showForm && !editingId && (
          <button
            type="button"
            onClick={() => {
              setShowForm(true);
              setFormName('');
              setFormProjectId('');
              setFormFormatSpecMarkdown('');
              setPendingFile(null);
            }}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Add template
          </button>
        )}
      </div>

      {(showForm || editingId !== null) && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-medium text-slate-900">
            {editingId ? 'Edit template' : 'New template'}
          </h2>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Name
              </label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Client A MoM format"
                className="mt-1 w-full max-w-md rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Tied to project (optional)
              </label>
              <select
                value={formProjectId}
                onChange={(e) =>
                  setFormProjectId(
                    e.target.value === '' ? '' : Number(e.target.value)
                  )
                }
                className="mt-1 w-full max-w-md rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">No project (use for any meeting)</option>
                {projects?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Format specification (markdown)
              </label>
              <textarea
                value={formFormatSpecMarkdown}
                onChange={(e) => setFormFormatSpecMarkdown(e.target.value)}
                placeholder={`Meeting Title:\nMeeting Attendee:\nMinutes taken by:\n## List of Items discussed or Action Items\n- `}
                rows={8}
                className="mt-1 w-full max-w-2xl rounded border border-slate-300 px-3 py-2 text-sm font-mono"
              />
              <p className="mt-1 text-xs text-slate-500">
                Define the exact structure the LLM must follow. Headings and labels will be preserved; the model will fill content from the transcript. When set, minutes are output as markdown in this format instead of the default JSON structure.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Template file (Word or text)
              </label>
              <input
                ref={templateFileInput}
                type="file"
                accept=".docx,.txt"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setPendingFile(f);
                }}
                className="mt-1 block w-full max-w-md text-sm text-slate-600 file:mr-2 file:rounded file:border-0 file:bg-indigo-50 file:px-3 file:py-1.5 file:text-indigo-700"
              />
              {editingId && templates?.find((t) => t.id === editingId)?.file_name && (
                <p className="mt-1 text-xs text-slate-500">
                  Current: {templates?.find((t) => t.id === editingId)?.file_name}. Upload a new file to replace.
                </p>
              )}
              {pendingFile && (
                <p className="mt-1 text-xs text-indigo-600">
                  Will upload: {pendingFile.name}
                </p>
              )}
              {editingId && templates?.find((t) => t.id === editingId)?.file_name ? (
                <div className="mt-2 rounded-md bg-slate-50 px-3 py-2">
                  <p className="text-xs font-medium text-slate-600">Detected sections (from template file)</p>
                  {templates?.find((t) => t.id === editingId)?.section_titles?.length ? (
                    <p className="mt-1 text-sm text-slate-800">
                      {templates?.find((t) => t.id === editingId)?.section_titles?.join(' → ')}
                    </p>
                  ) : (
                    <p className="mt-1 text-sm text-slate-500">No sections detected. Use Heading 1/2 in Word or put section titles on their own line (e.g. Attendees, Overview).</p>
                  )}
                </div>
              ) : null}
              <p className="mt-1 text-xs text-slate-500">
                Upload a .docx or .txt with your client&apos;s MoM format. The LLM
                will extract and match this structure automatically.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  if (editingId) {
                    updateMutation.mutate(editingId);
                    if (pendingFile) {
                      uploadMutation.mutate({ templateId: editingId, file: pendingFile });
                      setPendingFile(null);
                      if (templateFileInput.current) templateFileInput.current.value = '';
                    }
                  } else {
                    createMutation.mutate();
                  }
                }}
                disabled={createMutation.isPending || updateMutation.isPending || uploadMutation.isPending}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {editingId
                  ? pendingFile
                    ? 'Save & upload file'
                    : 'Save'
                  : pendingFile
                    ? 'Create & upload file'
                    : 'Create'}
              </button>
              <button
                type="button"
                onClick={cancelForm}
                className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-slate-500">Loading…</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Project
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Template file
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Detected sections
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!templates?.length ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-6 py-12 text-center text-slate-500"
                  >
                    No templates yet. Add one to match your clients&apos; MoM
                    formats.
                  </td>
                </tr>
              ) : (
                templates.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/50">
                    <td className="px-6 py-4 font-medium text-slate-900">
                      {t.name}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      {t.project_id
                        ? projects?.find((p) => p.id === t.project_id)?.name ??
                          `Project #${t.project_id}`
                        : '—'}
                    </td>
                    <td className="max-w-xs truncate px-6 py-4 text-sm text-slate-500">
                      {t.file_name || '—'}
                    </td>
                    <td className="max-w-md px-6 py-4 text-sm text-slate-600">
                      {t.section_titles?.length ? t.section_titles.join(', ') : '—'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => startEdit(t)}
                        className="text-sm text-indigo-600 hover:text-indigo-800"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm('Delete this template?'))
                            deleteMutation.mutate(t.id);
                        }}
                        className="ml-3 text-sm text-red-600 hover:text-red-800"
                      >
                        Delete
                      </button>
                    </td>
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
