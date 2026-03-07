const API_BASE = '/api';
const TOKEN_KEY = 'minuteslm_token';

function authHeaders(init?: RequestInit): HeadersInit {
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (typeof document !== 'undefined') {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export type MeetingStatus =
  | 'recording'
  | 'transcribing'
  | 'transcribed'
  | 'formatting'
  | 'formatted'
  | 'error';

export interface Meeting {
  id: number;
  project_id?: number | null;
  title: string;
  template_id?: number | null;
  created_at: string;
  audio_path: string | null;
  status: MeetingStatus;
  error_message: string | null;
  progress_message?: string | null;
  progress_percentage?: number | null;
  discussion_date_time?: string | null;
  attendee?: string | null;
  absentees?: string | null;
  minutes_taken_by?: string | null;
  summary_context?: string | null;
}

export interface MeetingCreatePayload {
  title: string;
  project_id: number;
  discussion_date_time?: string | null;
  attendee?: string | null;
  absentees?: string | null;
  minutes_taken_by?: string | null;
  summary_context?: string | null;
}

export interface TranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  id: number;
  meeting_id: number;
  raw_text: string;
  language: string | null;
  duration_seconds: number | null;
  segments?: TranscriptSegment[] | null;
}

export interface Minute {
  id: number;
  meeting_id: number;
  formatted_content: Record<string, unknown>;
  template_id: number | null;
  model_used: string | null;
  markdown: string | null;
}

export interface ActionItem {
  id: number;
  meeting_id: number;
  description: string;
  assignee: string | null;
  due_date: string | null;
  status: string;
}

export interface Project {
  id: number;
  user_id: number;
  name: string;
  default_template_id?: number | null;
  created_at: string;
}

export interface Template {
  id: number;
  user_id: number;
  project_id: number | null;
  name: string;
  structure: Record<string, string>;
  prompt_suffix: string | null;
  format_spec_markdown: string | null;
  file_name: string | null;
  section_titles: string[] | null;
  is_default: boolean;
}

export interface Speaker {
  id: number;
  user_id: number;
  name: string;
  audio_path: string | null;
  created_at: string;
}

export interface MeetingSpeakerSnippet {
  id: number;
  meeting_id: number;
  snippet_path: string;
  label: string;
  start_sec: number | null;
  end_sec: number | null;
  speaker_id: number | null;
  created_at: string;
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(init) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function fetchApiWithAuth<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(authHeaders(init) as Record<string, string>),
  };
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  }).then(async (r) => {
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || r.statusText);
    }
    return r.json();
  });
}

export interface Config {
  ollama_model: string;
}

export interface PurgeResult {
  deleted_rows: number;
  deleted_files: number;
  deleted_meetings: number;
  deleted_projects: number;
  deleted_speakers: number;
  deleted_templates: number;
}

export interface UserListItem {
  id: number;
  username: string;
  created_at: string;
  is_protected: boolean;
}

export const api = {
  config: {
    get: () => fetchApiWithAuth<Config>('/config'),
  },
  purge: () =>
    fetchApiWithAuth<PurgeResult>('/purge', { method: 'POST' }),
  users: {
    list: () => fetchApiWithAuth<UserListItem[]>('/users'),
    create: (username: string, password: string) =>
      fetchApiWithAuth<UserListItem>('/users', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),
    delete: (id: number) =>
      fetchApiWithAuth<unknown>(`/users/${id}`, { method: 'DELETE' }),
  },
  auth: {
    login: (username: string, password: string) =>
      fetchApi<{ access_token: string; user: { id: number; username: string } }>(
        '/auth/login',
        {
          method: 'POST',
          body: JSON.stringify({ username, password }),
        }
      ),
  },
  projects: {
    list: () => fetchApiWithAuth<Project[]>('/projects'),
    get: (id: number) => fetchApiWithAuth<Project>(`/projects/${id}`),
    create: (name: string) =>
      fetchApiWithAuth<Project>('/projects', {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    update: (id: number, data: { name?: string; default_template_id?: number | null }) =>
      fetchApiWithAuth<Project>(`/projects/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      fetchApiWithAuth<unknown>(`/projects/${id}`, { method: 'DELETE' }),
  },
  meetings: {
    list: (projectId: number) =>
      fetchApiWithAuth<Meeting[]>(`/meetings?project_id=${projectId}`),
    get: (id: number) => fetchApiWithAuth<Meeting>(`/meetings/${id}`),
    create: (payload: MeetingCreatePayload) =>
      fetchApiWithAuth<Meeting>('/meetings', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    upload: (id: number, file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return fetch(`${API_BASE}/meetings/${id}/upload`, {
        method: 'POST',
        body: fd,
        headers: authHeaders(),
      }).then(async (r) => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || r.statusText);
        }
        return r.json() as Promise<Meeting>;
      });
    },
    update: (
      id: number,
      data: {
        title?: string;
        template_id?: number | null;
        discussion_date_time?: string | null;
        attendee?: string | null;
        absentees?: string | null;
        minutes_taken_by?: string | null;
        summary_context?: string | null;
      }
    ) =>
      fetchApiWithAuth<Meeting>(`/meetings/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      fetchApiWithAuth<unknown>(`/meetings/${id}`, { method: 'DELETE' }),
    transcribe: (id: number) =>
      fetchApiWithAuth<Meeting>(`/meetings/${id}/transcribe`, {
        method: 'POST',
      }),
    retranscribe: (id: number) =>
      fetchApiWithAuth<Meeting>(`/meetings/${id}/retranscribe`, {
        method: 'POST',
      }),
    reformat: (id: number) =>
      fetchApiWithAuth<Meeting>(`/meetings/${id}/reformat`, {
        method: 'POST',
      }),
    getFormatPromptPreview: (meetingId: number) =>
      fetchApiWithAuth<{ prompt: string; model: string }>(
        `/meetings/${meetingId}/format-prompt-preview`
      ),
    detectedSpeakers: (meetingId: number) =>
      fetchApiWithAuth<MeetingSpeakerSnippet[]>(
        `/meetings/${meetingId}/detected-speakers`
      ),
    detectedSpeakerAudioUrl: (meetingId: number, snippetId: number) =>
      `${API_BASE}/meetings/${meetingId}/detected-speakers/${snippetId}/audio`,
    identifyDetectedSpeaker: (
      meetingId: number,
      snippetId: number,
      data: { speaker_id?: number; name?: string }
    ) =>
      fetchApiWithAuth<MeetingSpeakerSnippet>(
        `/meetings/${meetingId}/detected-speakers/${snippetId}/identify`,
        {
          method: 'PATCH',
          body: JSON.stringify(data),
        }
      ),
  },
  transcript: (meetingId: number) =>
    fetchApiWithAuth<Transcript | null>(`/meetings/${meetingId}/transcript`),
  minutes: (meetingId: number) =>
    fetchApiWithAuth<Minute | null>(`/meetings/${meetingId}/minutes`),
  actionItems: (meetingId: number) =>
    fetchApiWithAuth<ActionItem[]>(
      `/meetings/${meetingId}/action-items`
    ),
  speakers: {
    list: () => fetchApiWithAuth<Speaker[]>('/speakers'),
    create: (name: string) =>
      fetchApiWithAuth<Speaker>('/speakers', {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    createWithSample: (name: string, file: File) => {
      const fd = new FormData();
      fd.append('name', name);
      fd.append('file', file);
      return fetch(`${API_BASE}/speakers/with-sample`, {
        method: 'POST',
        body: fd,
        headers: authHeaders(),
      }).then(async (r) => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || r.statusText);
        }
        return r.json() as Promise<Speaker>;
      });
    },
    uploadSample: (speakerId: number, file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return fetch(`${API_BASE}/speakers/${speakerId}/sample`, {
        method: 'POST',
        body: fd,
        headers: authHeaders(),
      }).then(async (r) => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || r.statusText);
        }
        return r.json() as Promise<Speaker>;
      });
    },
    delete: (id: number) =>
      fetchApiWithAuth<unknown>(`/speakers/${id}`, { method: 'DELETE' }),
  },
  templates: {
    list: (projectId?: number) =>
      fetchApiWithAuth<Template[]>(
        projectId ? `/templates?project_id=${projectId}` : '/templates'
      ),
    get: (id: number) => fetchApiWithAuth<Template>(`/templates/${id}`),
    create: (data: {
      name: string;
      project_id?: number | null;
      prompt_suffix?: string | null;
      structure?: Record<string, string> | null;
      format_spec_markdown?: string | null;
    }) =>
      fetchApiWithAuth<Template>('/templates', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (
      id: number,
      data: {
        name?: string;
        project_id?: number | null;
        prompt_suffix?: string | null;
        structure?: Record<string, string> | null;
        format_spec_markdown?: string | null;
      }
    ) =>
      fetchApiWithAuth<Template>(`/templates/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      fetchApiWithAuth<unknown>(`/templates/${id}`, { method: 'DELETE' }),
    uploadFile: (id: number, file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return fetch(`${API_BASE}/templates/${id}/upload`, {
        method: 'POST',
        body: fd,
        headers: authHeaders(),
      }).then(async (r) => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || r.statusText);
        }
        return r.json() as Promise<Template>;
      });
    },
  },
};
