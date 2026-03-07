import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useRecording } from '../hooks/useRecording';
import { SpeakerListField, cleanSpeakerListForApi } from '../components/SpeakerListField';

function buildCreatePayload(form: {
  title: string;
  projectId: number;
  discussionDateTime: string;
  attendee: string;
  absentees: string;
  minutesTakenBy: string;
  summaryContext: string;
}) {
  return {
    title: form.title || 'Untitled Meeting',
    project_id: form.projectId,
    discussion_date_time: form.discussionDateTime
      ? new Date(form.discussionDateTime).toISOString()
      : null,
    attendee: cleanSpeakerListForApi(form.attendee) || null,
    absentees: cleanSpeakerListForApi(form.absentees) || null,
    minutes_taken_by: form.minutesTakenBy.trim() || null,
    summary_context: form.summaryContext.trim() || null,
  };
}

export function Record() {
  const location = useLocation();
  const stateProjectId = (location.state as { projectId?: number } | null)?.projectId;
  const [title, setTitle] = useState('Untitled Meeting');
  const [projectId, setProjectId] = useState<number | null>(stateProjectId ?? null);
  const [discussionDateTime, setDiscussionDateTime] = useState('');
  const [attendee, setAttendee] = useState('');
  const [absentees, setAbsentees] = useState('');
  const [minutesTakenBy, setMinutesTakenBy] = useState('');
  const [summaryContext, setSummaryContext] = useState('');
  const { isRecording, blob, start, stop, reset } = useRecording();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: api.projects.list,
  });

  const { data: speakers } = useQuery({
    queryKey: ['speakers'],
    queryFn: api.speakers.list,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.meetings.create(
        buildCreatePayload({
          title,
          projectId: projectId ?? 0,
          discussionDateTime,
          attendee,
          absentees,
          minutesTakenBy,
          summaryContext,
        })
      ),
    onSuccess: (meeting) => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/meetings/${meeting.id}`);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ meetingId, file }: { meetingId: number; file: File }) =>
      api.meetings.upload(meetingId, file),
    onSuccess: (meeting) => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      queryClient.invalidateQueries({ queryKey: ['meeting', meeting.id] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/meetings/${meeting.id}`);
    },
  });

  const canCreate = projectId != null;

  const handleCreateAndUpload = async () => {
    if (!blob || !projectId) return;
    const meeting = await api.meetings.create(
      buildCreatePayload({
        title,
        projectId,
        discussionDateTime,
        attendee,
        absentees,
        minutesTakenBy,
        summaryContext,
      })
    );
    const file = new File([blob], 'recording.webm', { type: blob.type });
    uploadMutation.mutate({ meetingId: meeting.id, file });
  };

  return (
    <div className="max-w-xl mx-auto space-y-8">
      <h1 className="text-2xl font-semibold text-slate-900">
        New Meeting
      </h1>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-sm font-medium text-slate-900 border-b border-slate-100 pb-2">
          Meeting details
        </h2>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Meeting Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            placeholder="e.g. Weekly sync"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Project Name
          </label>
          <select
            value={projectId ?? ''}
            onChange={(e) => setProjectId(e.target.value ? parseInt(e.target.value, 10) : null)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">Select a project</option>
            {projects?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Discussion Date & Time
          </label>
          <input
            type="datetime-local"
            value={discussionDateTime}
            onChange={(e) => setDiscussionDateTime(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <SpeakerListField
          value={attendee}
          onChange={setAttendee}
          label="Attendee"
          placeholder="Type to pick from Voice Samples or enter name"
          addButtonLabel="Add attendee"
          speakers={speakers}
          datalistId="record-attendee-speakers"
        />
        <SpeakerListField
          value={absentees}
          onChange={setAbsentees}
          label="Absentees"
          placeholder="Type name"
          addButtonLabel="Add absentee"
          speakers={speakers}
          datalistId="record-absentee-speakers"
          defaultOptionLabel="None"
        />
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Minutes taken by
          </label>
          <input
            type="text"
            value={minutesTakenBy}
            onChange={(e) => setMinutesTakenBy(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            placeholder="Name of note-taker"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Context for AI summary <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <textarea
            value={summaryContext}
            onChange={(e) => setSummaryContext(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            placeholder="e.g. participants, meeting overview, objective…"
          />
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h2 className="text-lg font-medium text-slate-900 mb-4">
          Record audio
        </h2>
        <p className="text-sm text-slate-500 mb-6">
          Record your meeting using the microphone, or upload an audio file from
          the meeting detail page.
        </p>

        <div className="flex items-center gap-4">
          {!isRecording && !blob && (
            <button
              onClick={start}
              className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-6 py-3 font-medium text-white hover:bg-red-700"
            >
              <span className="h-3 w-3 rounded-full bg-white" />
              Start recording
            </button>
          )}
          {isRecording && (
            <button
              onClick={stop}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-6 py-3 font-medium text-white hover:bg-slate-700"
            >
              <span className="h-3 w-3 rounded-full bg-red-400 animate-pulse" />
              Stop recording
            </button>
          )}
          {blob && (
            <>
              <span className="text-sm text-slate-600">
                {Math.round(blob.size / 1024)} KB recorded
              </span>
              <button
                onClick={() => {
                  handleCreateAndUpload();
                }}
                disabled={!canCreate || uploadMutation.isPending || createMutation.isPending}
                className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {uploadMutation.isPending || createMutation.isPending
                  ? 'Uploading…'
                  : 'Save & transcribe'}
              </button>
              <button
                onClick={reset}
                className="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 hover:bg-slate-50"
              >
                Record again
              </button>
            </>
          )}
        </div>
      </div>

      <div className="pt-4 border-t border-slate-200">
        <p className="text-sm text-slate-500 mb-2">
          Or create an empty meeting and upload an audio file later:
        </p>
        <button
          onClick={() => projectId != null && createMutation.mutate()}
          disabled={!canCreate || createMutation.isPending}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {createMutation.isPending ? 'Creating…' : 'Create meeting (no recording)'}
        </button>
      </div>
    </div>
  );
}
