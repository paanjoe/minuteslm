import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Meeting, Minute, MeetingSpeakerSnippet } from '../api/client';

const isProcessing = (m: Meeting | undefined) =>
  m?.status === 'transcribing' || m?.status === 'formatting';

function getMinutesDisplayText(m: Minute | null | undefined): string | null {
  if (!m) return null;
  if (m.markdown?.trim()) return m.markdown;
  const c = m.formatted_content as Record<string, unknown> | undefined;
  if (!c || typeof c !== 'object') return null;
  const parts: string[] = [];
  if (typeof c.overview === 'string') parts.push('## Overview\n\n' + c.overview);
  if (Array.isArray(c.discussion_highlights)) {
    parts.push('\n## Discussion Highlights\n');
    c.discussion_highlights.forEach((h: unknown) =>
      parts.push('- ' + (typeof h === 'string' ? h : String(h)))
    );
  }
  if (Array.isArray(c.action_items)) {
    parts.push('\n## Action Items\n');
    c.action_items.forEach((item: unknown) => {
      const o = item as Record<string, unknown>;
      let line = '- ' + (o.description ?? '');
      if (o.assignee) line += ' (@' + o.assignee + ')';
      if (o.due_date) line += ' — Due: ' + o.due_date;
      parts.push(line);
    });
  }
  if (Array.isArray(c.key_decisions)) {
    parts.push('\n## Key Decisions\n');
    c.key_decisions.forEach((d: unknown) => parts.push('- ' + (typeof d === 'string' ? d : String(d))));
  }
  return parts.length ? parts.join('\n') : null;
}

export function MeetingDetail() {
  const { id } = useParams<{ id: string }>();
  const meetingId = parseInt(id ?? '0', 10);
  const fileInput = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: meeting, isLoading: meetingLoading } = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => api.meetings.get(meetingId),
    enabled: meetingId > 0,
    refetchInterval: (q) =>
      isProcessing(q.state.data) ? 2000 : false,
  });

  const { data: transcript } = useQuery({
    queryKey: ['transcript', meetingId],
    queryFn: () => api.transcript(meetingId),
    enabled: meetingId > 0,
    refetchInterval: isProcessing(meeting) ? 2000 : false,
  });

  const { data: minutes } = useQuery({
    queryKey: ['minutes', meetingId],
    queryFn: () => api.minutes(meetingId),
    enabled: meetingId > 0,
    refetchInterval: isProcessing(meeting) ? 2000 : false,
  });

  const { data: templates } = useQuery({
    queryKey: ['templates'],
    queryFn: () => api.templates.list(),
  });

  const { data: detectedSpeakers } = useQuery({
    queryKey: ['detected-speakers', meetingId],
    queryFn: () => api.meetings.detectedSpeakers(meetingId),
    enabled: meetingId > 0,
  });

  const { data: speakers } = useQuery({
    queryKey: ['speakers'],
    queryFn: () => api.speakers.list(),
  });

  const updateMeetingMutation = useMutation({
    mutationFn: (data: { title?: string; template_id?: number | null }) =>
      api.meetings.update(meetingId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.meetings.upload(meetingId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['transcript', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['minutes', meetingId] });
    },
  });

  const canUpload =
    meeting &&
    !meeting.audio_path &&
    (meeting.status === 'recording' || meeting.status === 'error');

  const canRetranscribe =
    meeting?.audio_path &&
    !isProcessing(meeting) &&
    (meeting.status === 'formatted' || meeting.status === 'error');

  const canReformat =
    transcript &&
    !isProcessing(meeting) &&
    (meeting?.status === 'formatted' || meeting?.status === 'error');

  const deleteMutation = useMutation({
    mutationFn: () => api.meetings.delete(meetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      navigate('/');
    },
  });

  const retranscribeMutation = useMutation({
    mutationFn: () => api.meetings.retranscribe(meetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['transcript', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['minutes', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['detected-speakers', meetingId] });
    },
  });

  const reformatMutation = useMutation({
    mutationFn: () => api.meetings.reformat(meetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['minutes', meetingId] });
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadMutation.mutate(file);
    e.target.value = '';
  };

  const [identifyingSnippet, setIdentifyingSnippet] = useState<number | null>(null);
  const [newSpeakerName, setNewSpeakerName] = useState('');
  const identifyMutation = useMutation({
    mutationFn: ({
      snippetId,
      speakerId,
      name,
    }: {
      snippetId: number;
      speakerId?: number;
      name?: string;
    }) =>
      api.meetings.identifyDetectedSpeaker(meetingId, snippetId, {
        speaker_id: speakerId,
        name,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['detected-speakers', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['speakers'] });
      setIdentifyingSnippet(null);
      setNewSpeakerName('');
    },
  });

  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const copyToClipboard = async (label: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(label);
      setTimeout(() => setCopiedSection(null), 2000);
    } catch {
      // ignore
    }
  };

  const minutesText = getMinutesDisplayText(minutes);
  const transcriptText = transcript?.raw_text?.trim() || '';

  if (meetingLoading || !meeting) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <div className="animate-pulse text-slate-500">Loading…</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <Link
            to={meeting.project_id ? `/projects/${meeting.project_id}` : '/'}
            className="text-sm text-slate-500 hover:text-slate-700 mb-2 inline-block"
          >
            ← Back to list
          </Link>
          <h1 className="text-2xl font-semibold text-slate-900">
            {meeting.title}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              Minutes template:
              <select
                value={meeting.template_id ?? ''}
                onChange={(e) => {
                  const val =
                    e.target.value === '' ? null : Number(e.target.value);
                  updateMeetingMutation.mutate({ template_id: val });
                }}
                disabled={updateMeetingMutation.isPending}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">
                  Project default / standard
                </option>
                {templates
                  ?.filter(
                    (t) =>
                      !t.project_id || t.project_id === meeting.project_id
                  )
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {new Date(meeting.created_at).toLocaleString()} •{' '}
            <span className="capitalize">{meeting.status}</span>
            {meeting.progress_message && (
              <div className="mt-3 space-y-2">
                <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full animate-pulse"
                    style={{ width: '100%' }}
                  />
                </div>
                <span className="text-amber-700 text-sm font-medium block">
                  {meeting.progress_message}
                </span>
              </div>
            )}
            {meeting.error_message && (
              <span className="text-red-600 block mt-1">
                {meeting.error_message}
              </span>
            )}
          </p>
        </div>
        {canUpload && (
          <div>
            <input
              ref={fileInput}
              type="file"
              accept=".wav,.mp3,.m4a,.webm"
              className="hidden"
              onChange={handleFileChange}
            />
            <button
              onClick={() => fileInput.current?.click()}
              disabled={uploadMutation.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {uploadMutation.isPending ? 'Uploading…' : 'Upload audio'}
            </button>
          </div>
        )}
        <div className="flex gap-2">
          {canRetranscribe && (
            <button
              onClick={() => retranscribeMutation.mutate()}
              disabled={retranscribeMutation.isPending}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {retranscribeMutation.isPending ? 'Re-transcribing…' : 'Re-transcribe'}
            </button>
          )}
          {canReformat && (
            <button
              onClick={() => reformatMutation.mutate()}
              disabled={reformatMutation.isPending}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {reformatMutation.isPending ? 'Re-formatting…' : 'Re-format'}
            </button>
          )}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      </div>

      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="rounded-xl bg-white p-6 shadow-xl max-w-sm">
            <p className="font-medium text-slate-900">Delete this meeting?</p>
            <p className="mt-2 text-sm text-slate-500">
              This will permanently delete the meeting, transcript, minutes, and
              audio file.
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deleteMutation.mutate();
                  setShowDeleteConfirm(false);
                }}
                disabled={deleteMutation.isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-2 mb-4">
            <h2 className="text-lg font-medium text-slate-900">
              Raw Transcript
            </h2>
            {transcriptText ? (
              <button
                type="button"
                onClick={() => copyToClipboard('transcript', transcriptText)}
                className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {copiedSection === 'transcript' ? 'Copied!' : 'Copy'}
              </button>
            ) : null}
          </div>
          {transcript ? (
            <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans max-h-64 overflow-y-auto">
              {transcript.raw_text || '(empty)'}
            </pre>
          ) : (
            <p className="text-slate-500 italic">
              No transcript yet. Upload audio to transcribe.
            </p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-2 mb-4">
            <h2 className="text-lg font-medium text-slate-900">
              Formatted Minutes
            </h2>
            {minutesText ? (
              <button
                type="button"
                onClick={() => copyToClipboard('minutes', minutesText)}
                className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {copiedSection === 'minutes' ? 'Copied!' : 'Copy'}
              </button>
            ) : null}
          </div>
          {minutesText ? (
            <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans max-h-64 overflow-y-auto">
              {minutesText}
            </pre>
          ) : (
            <p className="text-slate-500 italic">
              Minutes will appear after transcription and LLM formatting.
            </p>
          )}
        </div>
      </div>

      {detectedSpeakers && detectedSpeakers.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-medium text-slate-900 mb-2">
            Detected speakers (review & identify)
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            Listen to each snippet and identify who spoke, or add as a new speaker.
          </p>
          <ul className="space-y-3">
            {detectedSpeakers.map((snippet: MeetingSpeakerSnippet) => (
              <li
                key={snippet.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-100 bg-slate-50/50 p-3"
              >
                <SnippetPlayButton meetingId={meetingId} snippetId={snippet.id} />
                <span className="font-medium text-slate-700">{snippet.label}</span>
                {snippet.start_sec != null && snippet.end_sec != null && (
                  <span className="text-xs text-slate-500">
                    {snippet.start_sec.toFixed(1)}s – {snippet.end_sec.toFixed(1)}s
                  </span>
                )}
                {snippet.speaker_id ? (
                  <span className="text-sm text-green-700">
                    Identified
                    {speakers?.find((s) => s.id === snippet.speaker_id)?.name && (
                      <> as {speakers?.find((s) => s.id === snippet.speaker_id)?.name}</>
                    )}
                  </span>
                ) : identifyingSnippet === snippet.id ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      className="rounded border border-slate-300 px-2 py-1 text-sm"
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === '') return;
                        const id = Number(v);
                        if (!Number.isNaN(id)) {
                          identifyMutation.mutate({
                            snippetId: snippet.id,
                            speakerId: id,
                          });
                        }
                      }}
                      disabled={identifyMutation.isPending}
                    >
                      <option value="">Choose existing speaker…</option>
                      {speakers?.map((s) => (
                        <option key={s.id} value={String(s.id)}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                    <span className="text-slate-400 text-sm">or</span>
                    <input
                      type="text"
                      placeholder="New speaker name"
                      value={newSpeakerName}
                      onChange={(e) => setNewSpeakerName(e.target.value)}
                      className="rounded border border-slate-300 px-2 py-1 text-sm w-40"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        identifyMutation.mutate({
                          snippetId: snippet.id,
                          name: newSpeakerName.trim() || undefined,
                        })
                      }
                      disabled={
                        !newSpeakerName.trim() || identifyMutation.isPending
                      }
                      className="rounded bg-indigo-600 px-3 py-1 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                      Add & link
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIdentifyingSnippet(null);
                        setNewSpeakerName('');
                      }}
                      className="text-sm text-slate-500 hover:text-slate-700"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIdentifyingSnippet(snippet.id)}
                    className="rounded border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100"
                  >
                    Who is this?
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SnippetPlayButton({
  meetingId,
  snippetId,
}: {
  meetingId: number;
  snippetId: number;
}) {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const play = async () => {
    if (playing || loading) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('minuteslm_token');
      const res = await fetch(
        api.meetings.detectedSpeakerAudioUrl(meetingId, snippetId),
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!res.ok) throw new Error('Failed to load audio');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setPlaying(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setPlaying(false);
        URL.revokeObjectURL(url);
      };
      await audio.play();
      setPlaying(true);
    } catch {
      setLoading(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={play}
      disabled={loading}
      className="rounded-full p-2 bg-slate-200 hover:bg-slate-300 text-slate-700 disabled:opacity-50"
      title="Play snippet"
    >
      {loading ? (
        <span className="text-xs">…</span>
      ) : playing ? (
        <span className="text-xs">⏸</span>
      ) : (
        <span className="text-xs">▶</span>
      )}
    </button>
  );
}
