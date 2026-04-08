export interface TypingUser {
  userId: string;
  username: string;
  avatar?: string | undefined;
}

interface TypingState {
  [roomId: string]: { [userId: string]: TypingUser };
}

let typingState = $state<TypingState>({});

const expiryTimers: Record<string, Record<string, ReturnType<typeof setTimeout>>> = {};

const EXPIRY_MS = 5000;
const EMPTY_ARRAY: TypingUser[] = [];

function resetExpiryTimer(roomId: string, userId: string) {
  if (!expiryTimers[roomId]) {
    expiryTimers[roomId] = {};
  }
  if (expiryTimers[roomId][userId]) {
    clearTimeout(expiryTimers[roomId][userId]);
  }
  expiryTimers[roomId][userId] = setTimeout(() => {
    removeTyping(roomId, userId);
  }, EXPIRY_MS);
}

function removeTyping(roomId: string, userId: string) {
  if (expiryTimers[roomId]?.[userId]) {
    clearTimeout(expiryTimers[roomId][userId]);
    delete expiryTimers[roomId][userId];
    if (Object.keys(expiryTimers[roomId]).length === 0) {
      delete expiryTimers[roomId];
    }
  }

  if (typingState[roomId]?.[userId]) {
    const { [userId]: _, ...rest } = typingState[roomId];
    if (Object.keys(rest).length === 0) {
      const { [roomId]: __, ...roomRest } = typingState;
      typingState = roomRest;
    } else {
      typingState = { ...typingState, [roomId]: rest };
    }
  }
}

export const typingIndicatorStore = {
  get state() {
    return typingState;
  },

  setTyping(roomId: string, user: TypingUser, isTyping: boolean) {
    if (isTyping) {
      if (typingState[roomId]?.[user.userId]) {
        // 使用者已在輸入中，只重置過期計時器
        resetExpiryTimer(roomId, user.userId);
        return;
      }

      typingState = {
        ...typingState,
        [roomId]: {
          ...(typingState[roomId] || {}),
          [user.userId]: user,
        },
      };
      resetExpiryTimer(roomId, user.userId);
    } else {
      removeTyping(roomId, user.userId);
    }
  },

  removeTyping,

  getTypingUsers(roomId: string): TypingUser[] {
    const room = typingState[roomId];
    if (!room) return EMPTY_ARRAY;
    return Object.values(room);
  },

  clearRoom(roomId: string) {
    if (expiryTimers[roomId]) {
      Object.values(expiryTimers[roomId]).forEach(clearTimeout);
      delete expiryTimers[roomId];
    }

    if (typingState[roomId]) {
      const { [roomId]: _, ...rest } = typingState;
      typingState = rest;
    }
  },

  clearAll() {
    Object.values(expiryTimers).forEach((roomTimers) => {
      Object.values(roomTimers).forEach(clearTimeout);
    });
    Object.keys(expiryTimers).forEach((key) => delete expiryTimers[key]);

    typingState = {};
  },
};
