import { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import toast from 'react-hot-toast';
import { api } from '../api/client';
import type { Meeting, Minute, MeetingSpeakerSnippet } from '../api/client';
import { SpeakerListField, cleanSpeakerListForApi } from '../components/SpeakerListField';
import { TOKEN_KEY } from '../constants/auth';

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
  const prevStatusRef = useRef<string | undefined>(undefined);
  const [detailTitle, setDetailTitle] = useState('');
  const [detailDiscussionDateTime, setDetailDiscussionDateTime] = useState('');
  const [detailAttendee, setDetailAttendee] = useState('');
  const [detailAbsentees, setDetailAbsentees] = useState('');
  const [detailMinutesTakenBy, setDetailMinutesTakenBy] = useState('');
  const [detailSummaryContext, setDetailSummaryContext] = useState('');

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

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: api.projects.list,
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

  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.config.get(),
  });

  const updateMeetingMutation = useMutation({
    mutationFn: (data: Parameters<typeof api.meetings.update>[1]) =>
      api.meetings.update(meetingId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
    },
  });

  useEffect(() => {
    if (!meeting) return;
    setDetailTitle(meeting.title ?? '');
    setDetailDiscussionDateTime(
      meeting.discussion_date_time
        ? new Date(meeting.discussion_date_time).toISOString().slice(0, 16)
        : ''
    );
    setDetailAttendee(meeting.attendee ?? '');
    setDetailAbsentees(meeting.absentees ?? '');
    setDetailMinutesTakenBy(meeting.minutes_taken_by ?? '');
    setDetailSummaryContext(meeting.summary_context ?? '');
  }, [meeting?.id, meeting?.title, meeting?.discussion_date_time, meeting?.attendee, meeting?.absentees, meeting?.minutes_taken_by, meeting?.summary_context]);

  useEffect(() => {
    prevStatusRef.current = undefined;
  }, [meetingId]);

  useEffect(() => {
    if (meeting?.status === 'transcribed' && prevStatusRef.current === 'transcribing' && transcript?.segments?.length) {
      const n = transcript.segments.length;
      toast.success(
        (t) => (
          <div className="flex flex-col gap-1">
            <p className="font-medium">Recording saved successfully!</p>
            <p className="text-sm text-slate-600">{n} transcript segment{n === 1 ? '' : 's'} saved.</p>
            <Link
              to={`/meetings/${meetingId}`}
              onClick={() => toast.dismiss(t.id)}
              className="mt-2 self-end rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
            >
              View Meeting
            </Link>
          </div>
        ),
        { duration: 6000 }
      );
    }
    prevStatusRef.current = meeting?.status;
  }, [meeting?.status, meetingId, transcript?.segments?.length]);

  const handleSaveMeetingDetails = () => {
    updateMeetingMutation.mutate({
      title: detailTitle || undefined,
      discussion_date_time: detailDiscussionDateTime
        ? new Date(detailDiscussionDateTime).toISOString()
        : null,
      attendee: cleanSpeakerListForApi(detailAttendee) || null,
      absentees: cleanSpeakerListForApi(detailAbsentees) || null,
      minutes_taken_by: detailMinutesTakenBy.trim() || null,
      summary_context: detailSummaryContext.trim() || null,
    });
  };

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

  const canTranscribe =
    meeting?.audio_path &&
    !isProcessing(meeting) &&
    !transcript;

  const canRetranscribe =
    meeting?.audio_path &&
    !isProcessing(meeting) &&
    !!transcript;

  const canReformat =
    !!transcript &&
    !isProcessing(meeting) &&
    (meeting?.status === 'transcribed' || meeting?.status === 'formatted' || meeting?.status === 'error');

  const deleteMutation = useMutation({
    mutationFn: () => api.meetings.delete(meetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      navigate('/');
    },
  });

  const transcribeMutation = useMutation({
    mutationFn: () => api.meetings.transcribe(meetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['transcript', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['minutes', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['detected-speakers', meetingId] });
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

  const [showPromptModal, setShowPromptModal] = useState(false);
  const [promptPreview, setPromptPreview] = useState<{ prompt: string; model: string } | null>(null);
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
  const copySegmentsJson = async () => {
    if (!transcript?.segments?.length) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(transcript.segments, null, 2));
      setCopiedSection('json');
      setTimeout(() => setCopiedSection(null), 2000);
    } catch {
      // ignore
    }
  };

  const minutesText = getMinutesDisplayText(minutes);
  const [minutesDraft, setMinutesDraft] = useState<string>('');
  const [minutesMode, setMinutesMode] = useState<'edit' | 'preview'>('preview');
  useEffect(() => {
    if (minutesText && !minutesDraft) {
      setMinutesDraft(minutesText);
    }
  }, [minutesText, minutesDraft]);
  const transcriptText = transcript?.raw_text?.trim() || '';
  const hasSegments = (transcript?.segments?.length ?? 0) > 0;
  const formatTimestamp = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

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
          <p className="text-sm text-slate-500 mt-1">
            {new Date(meeting.created_at).toLocaleString()} •{' '}
            <span className="capitalize">{meeting.status}</span>
            {meeting.progress_message && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-slate-600 text-sm font-medium">
                    {meeting.progress_message}
                  </span>
                  {typeof meeting.progress_percentage === 'number' && (
                    <span className="text-slate-500 text-sm tabular-nums">
                      {meeting.progress_percentage}%
                    </span>
                  )}
                </div>
                <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-[width] duration-300"
                    style={{
                      width: typeof meeting.progress_percentage === 'number'
                        ? `${Math.min(100, Math.max(0, meeting.progress_percentage))}%`
                        : '100%',
                    }}
                  />
                </div>
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
          {canTranscribe && (
            <button
              onClick={() => transcribeMutation.mutate()}
              disabled={transcribeMutation.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {transcribeMutation.isPending ? 'Transcribing…' : 'Transcribe'}
            </button>
          )}
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
              {reformatMutation.isPending ? 'Formatting…' : minutes ? 'Re-format' : 'Format'}
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

      {showPromptModal && promptPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="rounded-xl bg-white shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900">
                Qwen prompt (model: {promptPreview.model})
              </h3>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => copyToClipboard('prompt', promptPreview.prompt)}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  {copiedSection === 'prompt' ? 'Copied!' : 'Copy prompt'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowPromptModal(false);
                    setPromptPreview(null);
                  }}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Close
                </button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto p-4 text-xs text-slate-700 bg-slate-50 whitespace-pre-wrap font-mono">
              {promptPreview.prompt}
            </pre>
          </div>
        </div>
      )}

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

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-slate-900 mb-4">
          Meeting details
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Meeting Title
            </label>
            <input
              type="text"
              value={detailTitle}
              onChange={(e) => setDetailTitle(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              placeholder="e.g. Weekly sync"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Project Name
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700 text-sm">
              {meeting.project_id
                ? projects?.find((p) => p.id === meeting.project_id)?.name ?? `Project #${meeting.project_id}`
                : '—'}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Discussion Date & Time
            </label>
            <input
              type="datetime-local"
              value={detailDiscussionDateTime}
              onChange={(e) => setDetailDiscussionDateTime(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div className="sm:col-span-2">
            <SpeakerListField
              value={detailAttendee}
              onChange={setDetailAttendee}
              label="Attendee"
              placeholder="Type to pick from Voice Samples or enter name"
              addButtonLabel="Add attendee"
              speakers={speakers}
              datalistId="meeting-detail-attendee-speakers"
            />
          </div>
          <div className="sm:col-span-2">
            <SpeakerListField
              value={detailAbsentees}
              onChange={setDetailAbsentees}
              label="Absentees"
              placeholder="Type name"
              addButtonLabel="Add absentee"
              speakers={speakers}
              datalistId="meeting-detail-absentee-speakers"
              defaultOptionLabel="None"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Minutes taken by
            </label>
            <input
              type="text"
              value={detailMinutesTakenBy}
              onChange={(e) => setDetailMinutesTakenBy(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              placeholder="Name of note-taker"
            />
          </div>
        </div>
        <div className="mt-4">
          <button
            type="button"
            onClick={handleSaveMeetingDetails}
            disabled={updateMeetingMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {updateMeetingMutation.isPending ? 'Saving…' : 'Save meeting details'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left column: Transcript */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
            <h2 className="text-lg font-medium text-slate-900">
              Transcript
              {hasSegments && (
                <span className="ml-2 text-sm font-normal text-slate-500">
                  ({transcript!.segments!.length} segments)
                </span>
              )}
            </h2>
            <div className="flex gap-2">
              {transcriptText ? (
                <button
                  type="button"
                  onClick={() => copyToClipboard('transcript', transcriptText)}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  {copiedSection === 'transcript' ? 'Copied!' : 'Copy'}
                </button>
              ) : null}
              {hasSegments ? (
                <button
                  type="button"
                  onClick={copySegmentsJson}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  {copiedSection === 'json' ? 'Copied!' : 'Copy JSON'}
                </button>
              ) : null}
            </div>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {transcript ? (
              <>
                {hasSegments ? (
                  <div className="max-h-[28rem] space-y-1 overflow-y-auto text-sm text-slate-700">
                    {transcript.segments!.map((seg) => (
                      <div key={seg.id} className="flex gap-2">
                        <span className="shrink-0 font-mono text-slate-500">
                          [{formatTimestamp(seg.start)}]
                        </span>
                        <span>{seg.text || '\u00A0'}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap font-sans text-sm text-slate-700">
                    {transcript.raw_text || '(empty)'}
                  </pre>
                )}
              </>
            ) : (
              <p className="italic text-slate-500">
                No transcript yet. Upload audio to transcribe.
              </p>
            )}
          </div>
          <div className="border-t border-slate-200 p-4">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Add context for AI summary
            </label>
            <textarea
              value={detailSummaryContext}
              onChange={(e) => setDetailSummaryContext(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              placeholder="e.g. participants, meeting overview, objective…"
            />
            <p className="mt-1 text-xs text-slate-500">
              Saved with meeting details. Used when you click Format / Re-format.
            </p>
          </div>
        </div>

        {/* Right column: AI Summary / Formatted Minutes */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-medium text-slate-900">AI Summary</h2>
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                {config?.ollama_model ?? 'Ollama'}
              </span>
              <select
                title="Template used for Format / Re-format"
                value={meeting.template_id ?? ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? null : Number(e.target.value);
                  updateMeetingMutation.mutate({ template_id: val });
                }}
                disabled={updateMeetingMutation.isPending}
                className="rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">Template</option>
                {templates
                  ?.filter((t) => !t.project_id || t.project_id === meeting.project_id)
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </select>
              {canReformat && (
                <button
                  onClick={() => reformatMutation.mutate()}
                  disabled={reformatMutation.isPending}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {reformatMutation.isPending ? 'Formatting…' : minutes ? 'Re-format' : 'Format'}
                </button>
              )}
              {transcript && (
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const data = await api.meetings.getFormatPromptPreview(meetingId);
                      setPromptPreview(data);
                      setShowPromptModal(true);
                    } catch {
                      // ignore
                    }
                  }}
                  className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
                >
                  Prompt
                </button>
              )}
              {minutesText ? (
                <button
                  type="button"
                  onClick={() => copyToClipboard('minutes', minutesDraft || minutesText || '')}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  {copiedSection === 'minutes' ? 'Copied!' : 'Copy'}
                </button>
              ) : null}
            </div>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {meeting.status === 'formatting' || reformatMutation.isPending ? (
              <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                <svg className="h-10 w-10 animate-spin text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden>
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p className="mt-4 text-sm font-medium">Generating AI Summary…</p>
              </div>
            ) : minutesText ? (
              <div className="space-y-3">
                <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                  <button
                    type="button"
                    onClick={() => setMinutesMode('edit')}
                    className={`rounded-md px-2.5 py-1 ${minutesMode === 'edit' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setMinutesMode('preview')}
                    className={`rounded-md px-2.5 py-1 ${minutesMode === 'preview' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                  >
                    Preview
                  </button>
                </div>
                {minutesMode === 'edit' ? (
                  <>
                    <textarea
                      value={minutesDraft}
                      onChange={(e) => setMinutesDraft(e.target.value)}
                      rows={18}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      placeholder="Edit the generated markdown minutes here…"
                    />
                    <p className="text-xs text-slate-500">
                      Use standard markdown. The Copy button copies the content above.
                    </p>
                  </>
                ) : (
                  <div className="formatted-minutes-preview max-h-[28rem] overflow-y-auto rounded-lg border border-slate-200 bg-slate-50/50 px-5 py-4 text-sm text-slate-700 [&_h1]:mb-2 [&_h1]:mt-6 [&_h1]:border-b [&_h1]:border-slate-200 [&_h1]:pb-1 [&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-slate-900 [&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-slate-900 [&_h2:first-child]:mt-0 [&_h3]:mb-1 [&_h3]:mt-4 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-slate-900 [&_strong]:font-semibold [&_strong]:text-slate-800 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-6 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-6 [&_p]:my-2 [&_p]:leading-relaxed [&_p:last-child]:mb-0 [&_li]:my-0.5">
                    <ReactMarkdown>{minutesDraft || minutesText}</ReactMarkdown>
                  </div>
                )}
              </div>
            ) : (
              <p className="italic text-slate-500">
                Minutes will appear after transcription and Format.
              </p>
            )}
          </div>
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
      const token = localStorage.getItem(TOKEN_KEY);
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
