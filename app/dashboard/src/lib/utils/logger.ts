type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerOptions {
  enabled: boolean;
  level: LogLevel;
}

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3
};

class Logger {
  private options: LoggerOptions = {
    enabled: true,
    level: 'debug'
  };

  constructor(options?: Partial<LoggerOptions>) {
    this.options = { ...this.options, ...options };
  }

  private shouldLog(level: LogLevel): boolean {
    return this.options.enabled && LOG_LEVELS[level] >= LOG_LEVELS[this.options.level];
  }

  private formatMessage(level: LogLevel, message: string): string {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] [${level.toUpperCase()}] ${message}`;
  }

  debug(message: string, data?: any) {
    if (this.shouldLog('debug')) {
      const formattedMessage = this.formatMessage('debug', message);
      if (data) {
        console.debug(formattedMessage, data);
      } else {
        console.debug(formattedMessage);
      }
    }
  }

  info(message: string, data?: any) {
    if (this.shouldLog('info')) {
      const formattedMessage = this.formatMessage('info', message);
      if (data) {
        console.info(formattedMessage, data);
      } else {
        console.info(formattedMessage);
      }
    }
  }

  warn(message: string, data?: any) {
    if (this.shouldLog('warn')) {
      const formattedMessage = this.formatMessage('warn', message);
      if (data) {
        console.warn(formattedMessage, data);
      } else {
        console.warn(formattedMessage);
      }
    }
  }

  error(message: string, data?: any) {
    if (this.shouldLog('error')) {
      const formattedMessage = this.formatMessage('error', message);
      if (data) {
        console.error(formattedMessage, data);
      } else {
        console.error(formattedMessage);
      }
    }
  }
}

// Create a singleton instance
export const logger = new Logger({
  enabled: process.env.NODE_ENV !== 'production',
  level: process.env.NODE_ENV === 'production' ? 'error' : 'debug'
});