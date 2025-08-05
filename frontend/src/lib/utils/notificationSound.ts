/**
 * 通知聲音管理器
 * 使用 Web Audio API 生成更悅耳的通知聲音
 */

export class NotificationSoundManager {
  private audioContext: AudioContext | null = null;
  private enabled: boolean = true;
  private initialized: boolean = false;

  constructor() {
    // 延遲初始化 AudioContext，直到用戶第一次交互
    this.setupUserInteractionListener();
  }

  /**
   * 設置用戶交互監聽器來初始化 AudioContext
   */
  private setupUserInteractionListener() {
    if (typeof window === 'undefined') return;

    const initAudioContext = () => {
      if (!this.initialized && window.AudioContext) {
        this.audioContext = new AudioContext();
        this.initialized = true;
        
        // 移除事件監聽器，只需初始化一次
        document.removeEventListener('click', initAudioContext);
        document.removeEventListener('keydown', initAudioContext);
        document.removeEventListener('touchstart', initAudioContext);
      }
    };

    // 監聽用戶交互事件
    document.addEventListener('click', initAudioContext, { once: true });
    document.addEventListener('keydown', initAudioContext, { once: true });
    document.addEventListener('touchstart', initAudioContext, { once: true });
  }

  /**
   * 播放通知聲音
   */
  async playNotificationSound() {
    if (!this.enabled || !this.audioContext || !this.initialized) {
      return;
    }

    try {
      // 確保 AudioContext 是在用戶交互後啟動的
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const currentTime = this.audioContext.currentTime;
      
      // 創建兩個音符，形成和諧的聲音
      this.playNote(523.25, currentTime, 0.08);      // C5
      this.playNote(659.25, currentTime + 0.08, 0.08); // E5
      this.playNote(783.99, currentTime + 0.16, 0.12); // G5
      
    } catch (error) {
      console.error('Failed to play notification sound:', error);
    }
  }

  /**
   * 播放單個音符
   */
  private playNote(frequency: number, startTime: number, duration: number) {
    if (!this.audioContext) return;

    // 創建振盪器（聲音源）
    const oscillator = this.audioContext.createOscillator();
    const gainNode = this.audioContext.createGain();

    // 設置音色為正弦波（更柔和）
    oscillator.type = 'sine';
    oscillator.frequency.value = frequency;

    // 設置音量包絡
    gainNode.gain.setValueAtTime(0, startTime);
    gainNode.gain.linearRampToValueAtTime(0.2, startTime + 0.01); // 快速淡入
    gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration); // 緩慢淡出

    // 連接節點
    oscillator.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    // 播放
    oscillator.start(startTime);
    oscillator.stop(startTime + duration);
  }

  /**
   * 播放錯誤聲音
   */
  async playErrorSound() {
    if (!this.enabled || !this.audioContext) {
      return;
    }

    try {
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const currentTime = this.audioContext.currentTime;
      
      // 播放一個下降的音調
      this.playNote(440, currentTime, 0.1);       // A4
      this.playNote(349.23, currentTime + 0.1, 0.15); // F4
      
    } catch (error) {
      console.error('Failed to play error sound:', error);
    }
  }

  /**
   * 播放成功聲音
   */
  async playSuccessSound() {
    if (!this.enabled || !this.audioContext) {
      return;
    }

    try {
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const currentTime = this.audioContext.currentTime;
      
      // 播放上升的音調
      this.playNote(523.25, currentTime, 0.1);       // C5
      this.playNote(659.25, currentTime + 0.1, 0.1); // E5
      this.playNote(783.99, currentTime + 0.2, 0.15); // G5
      this.playNote(1046.5, currentTime + 0.35, 0.2); // C6
      
    } catch (error) {
      console.error('Failed to play success sound:', error);
    }
  }

  /**
   * 啟用/禁用聲音
   */
  setEnabled(enabled: boolean) {
    this.enabled = enabled;
  }

  /**
   * 檢查聲音是否啟用
   */
  isEnabled(): boolean {
    return this.enabled;
  }
}

// 創建單例實例
export const notificationSound = new NotificationSoundManager();