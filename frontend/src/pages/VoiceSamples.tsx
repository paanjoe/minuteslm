import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useRecording } from '../hooks/useRecording';

export function VoiceSamples() {
  const queryClient = useQueryClient();
  const { data: speakers, isLoading } = useQuery({
    queryKey: ['speakers'],
    queryFn: api.speakers.list,
  });
  const [newSpeakerName, setNewSpeakerName] = useState('');
  const [recordingFor, setRecordingFor] = useState<number | null>(null);
  const [showWhoIsThis, setShowWhoIsThis] = useState(false);
  const [uploadForId, setUploadForId] = useState<number | null>(null);
  const uploadedForRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { blob, start, stop, reset } = useRecording();

  const createSpeakerMutation = useMutation({
    mutationFn: (name: string) => api.speakers.create(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['speakers'] });
      setNewSpeakerName('');
    },
  });

  const createWithSampleMutation = useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) =>
      api.speakers.createWithSample(name, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['speakers'] });
      setShowWhoIsThis(false);
      reset();
    },
  });

  const uploadSampleMutation = useMutation({
    mutationFn: ({ speakerId, file }: { speakerId: number; file: File }) =>
      api.speakers.uploadSample(speakerId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['speakers'] });
      setRecordingFor(null);
      setUploadForId(null);
      reset();
    },
  });

  useEffect(() => {
    if (recordingFor != null && blob && uploadedForRef.current !== recordingFor && !showWhoIsThis) {
      uploadedForRef.current = recordingFor;
      const file = new File([blob], 'sample.webm', { type: blob.type });
      uploadSampleMutation.mutate({ speakerId: recordingFor, file });
    }
  }, [blob, recordingFor, showWhoIsThis]);

  useEffect(() => {
    if (recordingFor == null) uploadedForRef.current = null;
  }, [recordingFor]);

  const handleRecordFor = (speakerId: number) => {
    setRecordingFor(speakerId);
    setShowWhoIsThis(false);
    start();
  };

  const handleRecordUnknown = () => {
    setRecordingFor(-1);
    setShowWhoIsThis(false);
    start();
  };

  const handleStopRecord = () => {
    stop();
    if (recordingFor === -1) setShowWhoIsThis(true);
  };

  const handleWhoIsThisSubmit = (name: string) => {
    if (!blob || !name.trim()) return;
    const file = new File([blob], 'sample.webm', { type: blob.type });
    createWithSampleMutation.mutate({ name: name.trim(), file });
    setRecordingFor(null);
  };

  const handleUploadClick = (speakerId: number) => {
    setUploadForId(speakerId);
    fileInputRef.current?.click();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || uploadForId == null) return;
    uploadSampleMutation.mutate({ speakerId: uploadForId, file });
    setUploadForId(null);
    e.target.value = '';
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Voice samples</h1>
      <p className="text-slate-500">
        Add people and their voice samples so we can recognise who is speaking. You can record a
        sample, upload an audio file, or record first and then name the person (“Who is this?”).
      </p>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <h2 className="font-medium text-amber-900">Record unknown speaker</h2>
        <p className="mt-1 text-sm text-amber-800">
          Heard someone in a recording you don’t have a profile for? Record a short clip, then we’ll
          ask you who it is.
        </p>
        {recordingFor === -1 ? (
          <>
            <span className="mt-3 inline-block text-sm text-amber-800">Recording…</span>
            <button
              onClick={handleStopRecord}
              className="ml-2 rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Stop
            </button>
          </>
        ) : (
          <button
            onClick={handleRecordUnknown}
            disabled={recordingFor != null}
            className="mt-3 rounded-lg border border-amber-400 bg-amber-100 px-4 py-2 text-sm font-medium text-amber-900 hover:bg-amber-200 disabled:opacity-50"
          >
            Record clip, then name
          </button>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".wav,.mp3,.m4a,.webm,.ogg"
        className="hidden"
        onChange={handleFileSelect}
      />

      {showWhoIsThis && blob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-medium text-slate-900">Who is this?</h3>
            <p className="mt-1 text-sm text-slate-500">Name this speaker so we can save the sample.</p>
            <input
              type="text"
              placeholder="e.g. John, Sarah"
              className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleWhoIsThisSubmit((e.target as HTMLInputElement).value);
              }}
              id="who-is-this-name"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowWhoIsThis(false);
                  setRecordingFor(null);
                  reset();
                }}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleWhoIsThisSubmit((document.getElementById('who-is-this-name') as HTMLInputElement)?.value)}
                disabled={createWithSampleMutation.isPending}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {createWithSampleMutation.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-slate-900">Your speakers</h2>
        {isLoading ? (
          <p className="mt-4 text-slate-500">Loading…</p>
        ) : (
          <div className="mt-4 space-y-3">
            {speakers?.map((s) => (
              <div
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
              >
                <span className="font-medium text-slate-800">{s.name}</span>
                <div className="flex items-center gap-2">
                  {s.audio_path ? (
                    <span className="text-xs text-emerald-600">Sample saved</span>
                  ) : null}
                  <button
                    onClick={() => handleUploadClick(s.id)}
                    disabled={uploadSampleMutation.isPending}
                    className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                  >
                    Upload sample
                  </button>
                  {recordingFor === s.id ? (
                    <>
                      <button
                        onClick={() => stop()}
                        disabled={uploadSampleMutation.isPending}
                        className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                      >
                        {uploadSampleMutation.isPending ? 'Saving…' : 'Stop'}
                      </button>
                      <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                    </>
                  ) : (
                    <button
                      onClick={() => handleRecordFor(s.id)}
                      disabled={recordingFor != null}
                      className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                    >
                      Record sample
                    </button>
                  )}
                </div>
              </div>
            ))}
            <div className="flex gap-2 pt-2">
              <input
                type="text"
                value={newSpeakerName}
                onChange={(e) => setNewSpeakerName(e.target.value)}
                placeholder="Add person by name (e.g. John)"
                className="rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                onClick={() => createSpeakerMutation.mutate(newSpeakerName.trim() || 'Unnamed')}
                disabled={createSpeakerMutation.isPending || !newSpeakerName.trim()}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Add speaker
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
