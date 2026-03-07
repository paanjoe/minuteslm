import type { Speaker } from '../api/client';

const OTHER_VALUE = '__OTHER__';

/** Use when sending attendee/absentees to API: removes __OTHER__ placeholder and trims. */
export function cleanSpeakerListForApi(value: string): string {
  if (!value) return '';
  return value
    .split('\n')
    .filter((line) => line !== OTHER_VALUE)
    .map((l) => l.trim())
    .filter(Boolean)
    .join('\n');
}

function parseList(value: string, defaultOptionLabel?: string): string[] {
  if (!value) return defaultOptionLabel ? [defaultOptionLabel] : [''];
  if (defaultOptionLabel && value === OTHER_VALUE) {
    return [defaultOptionLabel, OTHER_VALUE];
  }
  const items = value.split(/\n/);
  const normalized = defaultOptionLabel
    ? items.map((i) => (i === '' ? defaultOptionLabel : i))
    : items;
  return normalized.length ? normalized : defaultOptionLabel ? [defaultOptionLabel] : [''];
}

function joinList(items: string[], defaultOptionLabel?: string): string {
  const mapped = defaultOptionLabel
    ? items.map((i) => (i === defaultOptionLabel ? '' : i))
    : items;
  return mapped.join('\n');
}

interface SpeakerListFieldProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  addButtonLabel?: string;
  speakers: Speaker[] | undefined;
  datalistId: string;
  /** e.g. "None" for absentees: first option in dropdown, excluded from saved value */
  defaultOptionLabel?: string;
}

export function SpeakerListField({
  value,
  onChange,
  label,
  placeholder = 'Type name',
  addButtonLabel = 'Add row',
  speakers,
  datalistId,
  defaultOptionLabel,
}: SpeakerListFieldProps) {
  const items = parseList(value, defaultOptionLabel);
  const speakerNames = speakers?.map((s) => s.name) ?? [];

  const setItem = (index: number, text: string) => {
    const next = [...items];
    next[index] = text;
    onChange(joinList(next, defaultOptionLabel));
  };

  const removeItem = (index: number) => {
    const next = items.filter((_, i) => i !== index);
    onChange(joinList(next.length ? next : defaultOptionLabel ? [defaultOptionLabel] : [''], defaultOptionLabel));
  };

  const addRow = () => {
    const newItem = defaultOptionLabel ? defaultOptionLabel : '';
    onChange(joinList([...items, newItem], defaultOptionLabel));
  };

  const isSelectRow = (item: string) =>
    speakerNames.includes(item) ||
    (!!defaultOptionLabel && (item === defaultOptionLabel || item === ''));

  const selectValue = (item: string) =>
    defaultOptionLabel && item === '' ? defaultOptionLabel : item;

  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {label}
      </label>
      <datalist id={datalistId}>
        {speakers?.map((s) => (
          <option key={s.id} value={s.name} />
        ))}
      </datalist>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={index} className="flex gap-2 items-center">
            {isSelectRow(item) ? (
              <select
                value={selectValue(item)}
                onChange={(e) => setItem(index, e.target.value)}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 bg-white"
              >
                {defaultOptionLabel && (
                  <option value={defaultOptionLabel}>{defaultOptionLabel}</option>
                )}
                {speakerNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
                <option value={OTHER_VALUE}>— Other —</option>
              </select>
            ) : (
              <input
                type="text"
                value={item === OTHER_VALUE ? '' : item}
                onChange={(e) => setItem(index, e.target.value)}
                list={datalistId}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                placeholder={placeholder}
              />
            )}
            <button
              type="button"
              onClick={() => removeItem(index)}
              disabled={items.length <= 1}
              className="shrink-0 rounded p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40 disabled:hover:bg-transparent"
              title="Remove row"
              aria-label="Remove row"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={addRow}
          className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
        >
          + {addButtonLabel}
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Choose from Voice Samples or “— Other —” to type a name.
      </p>
    </div>
  );
}
