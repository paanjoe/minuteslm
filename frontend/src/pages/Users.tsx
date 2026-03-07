import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { api } from '../api/client';
import type { UserListItem } from '../api/client';

export function Users() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const { data: users, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: api.users.list,
  });

  const createMutation = useMutation({
    mutationFn: () => api.users.create(username.trim(), password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setUsername('');
      setPassword('');
      toast.success('User created. They can log in with that username and password.');
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.users.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User removed.');
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) {
      toast.error('Username required');
      return;
    }
    if (!password) {
      toast.error('Password required');
      return;
    }
    createMutation.mutate();
  };

  if (error) {
    return (
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold text-slate-900">Users</h1>
        <p className="mt-2 text-slate-600">Only the admin can manage users.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Users</h1>
      <p className="text-slate-600">
        Add colleagues so they can log in with their own username and password. The default admin user cannot be removed.
      </p>

      <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4">
        <div>
          <label className="block text-sm font-medium text-slate-700">Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-40 rounded border border-slate-300 px-2 py-1.5 text-sm"
            placeholder="colleague"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-40 rounded border border-slate-300 px-2 py-1.5 text-sm"
            placeholder="••••••••"
          />
        </div>
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {createMutation.isPending ? 'Adding…' : 'Add user'}
        </button>
      </form>

      <div className="rounded-lg border border-slate-200 bg-white">
        <h2 className="border-b border-slate-200 px-4 py-2 text-sm font-medium text-slate-700">All users</h2>
        {isLoading ? (
          <p className="p-4 text-slate-500">Loading…</p>
        ) : (
          <ul className="divide-y divide-slate-200">
            {(users ?? []).map((u: UserListItem) => (
              <li key={u.id} className="flex items-center justify-between px-4 py-2">
                <div>
                  <span className="font-medium text-slate-900">{u.username}</span>
                  {u.is_protected && (
                    <span className="ml-2 text-xs text-slate-500">(default admin – cannot remove)</span>
                  )}
                </div>
                <button
                  type="button"
                  disabled={u.is_protected}
                  onClick={() => {
                    if (u.is_protected) return;
                    if (window.confirm(`Remove user "${u.username}"?`)) deleteMutation.mutate(u.id);
                  }}
                  className="rounded px-2 py-1 text-sm text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
