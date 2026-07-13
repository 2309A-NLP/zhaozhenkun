const STORAGE_KEY = 'edu-agent-workspace-state';

export const store = {
  read() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  },
  write(partial) {
    const next = { ...this.read(), ...partial };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  },
  clear() {
    localStorage.removeItem(STORAGE_KEY);
  },
};
