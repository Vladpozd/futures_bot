
"""
Настраиваемый логгер для торгового бота.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger

from config.settings import settings


class BotLogger:
    """Кастомный логгер для торгового бота."""
    
    def __init__(self):
        self.logger = logger
        self.log_file = None
        
        # Сначала патчим методы
        self.info = self.logger.info
        self.warning = self.logger.warning
        self.error = self.logger.error
        self.debug = self.logger.debug
        self.critical = self.logger.critical
        self.exception = self.logger.exception
        self.success = self._custom_success
        
        # Затем настраиваем
        self._setup_defaults()
    
    def _setup_defaults(self):
        """Настройка логгера по умолчанию."""
        # Удаляем стандартный обработчик
        self.logger.remove()
        
        # Формат логов
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        # Консольный вывод с цветами
        self.logger.add(
            sys.stdout,
            format=log_format,
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
        
        # Файловый вывод
        self._setup_file_logging()
    
    def _setup_file_logging(self):
        """Настройка записи логов в файл."""
        try:
            log_path = Path(settings.LOG_FILE)
            log_path.parent.mkdir(exist_ok=True)
            
            # Формат для файла (без цветов)
            file_format = (
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            )
            
            self.logger.add(
                str(log_path),
                format=file_format,
                level="DEBUG",
                rotation="10 MB",
                retention="30 days",
                compression="zip",
                backtrace=True,
                diagnose=True
            )
            
            self.log_file = log_path
            self.info(f"Логирование в файл настроено: {log_path}")
            
        except Exception as e:
            print(f"Ошибка настройки файлового логирования: {e}")
    
    def _custom_success(self, message: str):
        """Кастомный метод для успешных действий."""
        self.logger.info(f"✅ {message}")
    
    def setup_logger(self, 
                    log_level: str = None,
                    log_file: str = None,
                    console_output: bool = True) -> None:
        """Перенастроить логгер."""
        # Удаляем все обработчики
        self.logger.remove()
        
        # Уровень логирования
        level = log_level or settings.LOG_LEVEL
        
        # Формат логов
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        # Консольный вывод
        if console_output:
            self.logger.add(
                sys.stdout,
                format=log_format,
                level=level,
                colorize=True,
                backtrace=True,
                diagnose=True
            )
        
        # Файловый вывод
        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(exist_ok=True)
                
                file_format = (
                    "{time:YYYY-MM-DD HH:mm:ss} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                )
                
                self.logger.add(
                    str(log_path),
                    format=file_format,
                    level="DEBUG",
                    rotation="10 MB",
                    retention="30 days",
                    compression="zip",
                    backtrace=True,
                    diagnose=True
                )
                
                self.log_file = log_path
                self.info(f"Логирование в файл настроено: {log_path}")
                
            except Exception as e:
                self.logger.error(f"Ошибка настройки файлового логирования: {e}")
    
    def log_to_file(self, 
                   level: str, 
                   message: str, 
                   extra: Optional[Dict[str, Any]] = None):
        """Записать сообщение в файл логов."""
        if not self.log_file:
            return
        
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level.upper(),
                "message": message
            }
            
            if extra:
                log_entry.update(extra)
            
            if level.upper() == "INFO":
                self.logger.info(message)
            elif level.upper() == "WARNING":
                self.logger.warning(message)
            elif level.upper() == "ERROR":
                self.logger.error(message)
            elif level.upper() == "DEBUG":
                self.logger.debug(message)
            elif level.upper() == "CRITICAL":
                self.logger.critical(message)
            elif level.upper() == "SUCCESS":
                self._custom_success(message)
                
        except Exception as e:
            print(f"Ошибка записи в лог-файл: {e}")
    
    def log_trade(self, 
                 ticker: str,
                 action: str,
                 quantity: int,
                 price: float,
                 pnl: float = 0.0,
                 reason: str = ""):
        """Записать информацию о торговой операции."""
        trade_log = {
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "price": price,
            "pnl": pnl,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        emoji = {
            "OPEN": "📈",
            "CLOSE": "📉",
            "STOP": "🛑",
            "TAKE": "💰"
        }.get(action, "📊")
        
        message = f"{emoji} {action}: {ticker} {quantity} лотов по {price:.2f}"
        if pnl != 0:
            message += f", PnL: {pnl:+.0f}₽"
        if reason:
            message += f" ({reason})"
        
        self.info(message)
        self.log_to_file("INFO", f"Trade: {message}", trade_log)
    
    def log_analysis(self, 
                    ticker: str,
                    timeframe: str,
                    probability: float,
                    signal: str,
                    confidence: float):
        """Записать результат анализа."""
        analysis_log = {
            "ticker": ticker,
            "timeframe": timeframe,
            "probability": probability,
            "signal": signal,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        
        signal_emoji = {
            "BUY": "🟢",
            "SELL": "🔴",
            "NEUTRAL": "⚪"
        }.get(signal, "⚪")
        
        message = (f"{signal_emoji} Анализ {ticker} ({timeframe}): "
                  f"{signal} с вероятностью {probability:.1%}, уверенность {confidence:.1f}%")
        
        if probability > 0.7 and signal != "NEUTRAL":
            self.info(message)
        else:
            self.debug(message)
        
        self.log_to_file("DEBUG", f"Analysis: {message}", analysis_log)
    
    def log_portfolio_update(self,
                           deposit: float,
                           pnl: float,
                           positions: int,
                           win_rate: float):
        """Записать обновление портфеля."""
        portfolio_log = {
            "deposit": deposit,
            "pnl": pnl,
            "positions": positions,
            "win_rate": win_rate,
            "timestamp": datetime.now().isoformat()
        }
        
        message = (f"💰 Портфель: депозит {deposit:.0f}₽, PnL {pnl:+.0f}₽, "
                  f"позиций: {positions}, винрейт: {win_rate:.1f}%")
        
        self.info(message)
        self.log_to_file("INFO", f"Portfolio: {message}", portfolio_log)


# Глобальный экземпляр логгера
log = BotLogger()


def setup_logger(log_level: str = None, 
                log_file: str = None,
                console_output: bool = True) -> BotLogger:
    """Настроить логгер."""
    log.setup_logger(log_level, log_file, console_output)
    return log


if __name__ == "__main__":
    # Тест логгера
    print("\n" + "="*60)
    print("🧪 ТЕСТ ЛОГГЕРА")
    print("="*60)
    
    log.info("Тестовое информационное сообщение")
    log.success("Тестовое сообщение об успехе")
    log.warning("Тестовое предупреждение")
    log.error("Тестовая ошибка")
    log.debug("Тестовое отладочное сообщение")
    
    log.log_trade("Si-3.26", "OPEN", 1, 75000.5, 0, "Сильный сигнал покупки")
    log.log_analysis("RTS-3.26", "1h", 0.85, "BUY", 90.5)
    log.log_portfolio_update(10500.0, 500.0, 2, 65.5)
    
    print("\n" + "="*60)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("="*60)
