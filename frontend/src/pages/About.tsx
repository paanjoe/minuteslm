import { useState } from 'react';
import toast from 'react-hot-toast';
import { api } from '../api/client';
import { useQueryClient } from '@tanstack/react-query';

export function About() {
  const [purging, setPurging] = useState(false);
  const queryClient = useQueryClient();

  async function handlePurge() {
    if (!window.confirm('Delete all projects, meetings, transcripts, speakers, templates, and uploaded files? This cannot be undone.')) return;
    setPurging(true);
    try {
      const result = await api.purge();
      toast.success(`Purged ${result.deleted_rows} DB rows and ${result.deleted_files} files.`);
      queryClient.clear();
      window.location.href = '/';
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Purge failed');
    } finally {
      setPurging(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">About MinutesLM</h1>
      <p className="text-slate-600 leading-relaxed">
        MinutesLM is a <strong>privacy-first</strong> meeting minutes assistant. All processing runs on your own infrastructure: transcription (Whisper), formatting (Ollama), and storage (PostgreSQL) stay local. No cloud required—your data never leaves your control.
      </p>
      <p className="text-slate-600 leading-relaxed">
        Built for professionals and teams who need structured meeting notes and action items without sending sensitive conversations to third-party services. Self-host it and keep full data sovereignty.
      </p>
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <h2 className="text-sm font-semibold text-red-800">Danger zone</h2>
        <p className="mt-1 text-sm text-red-700">
          Permanently delete all your data: projects, meetings, transcripts, minutes, speakers, templates, and all uploaded files.
        </p>
        <button
          type="button"
          onClick={handlePurge}
          disabled={purging}
          className="mt-3 rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {purging ? 'Purging…' : 'Purge all data'}
        </button>
      </div>
    </div>
  );
}
