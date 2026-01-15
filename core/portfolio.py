"""
Управление портфелем, депозитом и вариационной маржой.
Ежедневное обновление депозита с учетом прибыли.
"""
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal

from config.settings import settings
from utils.logger import log


@dataclass
class PortfolioStats:
    """Статистика портфеля за день"""
    date: str
    initial_deposit: float
    current_deposit: float
    daily_pnl: float
    total_pnl: float
    total_commissions: float
    vm_accruals: float
    open_positions: int
    closed_positions: int
    win_rate: float


class PortfolioManager:
    """
    Менеджер портфеля с депозитом 10,000₽
    Ежедневное обновление депозита с учетом прибыли
    Учет вариационной маржи
    """
    
    def __init__(self, initial_deposit: float = None):
        self.initial_deposit = initial_deposit or settings.INITIAL_DEPOSIT
        self.current_deposit = self.initial_deposit
        self.available_deposit = self.current_deposit  # Доступно для торговли
        self.blocked_deposit = 0.0  # Заблокировано в открытых позициях
        
        # Статистика
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.total_commissions = 0.0
        self.vm_accruals = 0.0
        self.open_positions_count = 0
        self.closed_positions_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # История
        self.stats_file = settings.DATA_DIR / "portfolio_stats.json"
        self.stats_history: List[PortfolioStats] = []
        
        self._load_stats()
        self._check_daily_reset()
        
        log.info(f"Инициализация портфеля. Депозит: {self.current_deposit:.2f}₽")
    
    def _load_stats(self):
        """Загрузить историю статистики"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.stats_history = [PortfolioStats(**item) for item in data]
                log.debug(f"Загружена история из {self.stats_file}")
        except Exception as e:
            log.warning(f"Ошибка загрузки статистики: {e}")
    
    def _save_stats(self):
        """Сохранить историю статистики"""
        try:
            stats_data = [asdict(stats) for stats in self.stats_history]
            with open(self.stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2)
        except Exception as e:
            log.error(f"Ошибка сохранения статистики: {e}")
    
    def _check_daily_reset(self):
        """Проверить, нужно ли сбросить дневную статистику (новый день)"""
        today = date.today().isoformat()
        
        if self.stats_history:
            last_stat = self.stats_history[-1]
            if last_stat.date == today:
                # Уже есть запись на сегодня
                self.daily_pnl = last_stat.daily_pnl
                return
        
        # Новый день - сбрасываем daily_pnl и обновляем депозит
        self._start_new_day()
    
    def _start_new_day(self):
        """Начать новый торговый день"""
        today = date.today().isoformat()
        
        # Сохраняем статистику за вчера
        if self.stats_history:
            yesterday_stat = self.stats_history[-1]
            if yesterday_stat.date != today:
                # Обновляем депозит с учетом вчерашней прибыли
                if yesterday_stat.daily_pnl > 0:
                    self.current_deposit += yesterday_stat.daily_pnl
                    self.available_deposit = self.current_deposit
                    log.info(f"💰 Обновлен депозит: {self.current_deposit:.2f}₽ "
                            f"(+{yesterday_stat.daily_pnl:.2f}₽)")
        
        # Добавляем запись на сегодня
        today_stat = PortfolioStats(
            date=today,
            initial_deposit=self.current_deposit,
            current_deposit=self.current_deposit,
            daily_pnl=0.0,
            total_pnl=self.total_pnl,
            total_commissions=self.total_commissions,
            vm_accruals=self.vm_accruals,
            open_positions=self.open_positions_count,
            closed_positions=self.closed_positions_count,
            win_rate=self.win_rate
        )
        
        self.stats_history.append(today_stat)
        self._save_stats()
        
        log.info(f"📅 Начат новый торговый день {today}. "
                f"Депозит: {self.current_deposit:.2f}₽")
    
    @property
    def win_rate(self) -> float:
        """Рассчитать винрейт"""
        total_trades = self.winning_trades + self.losing_trades
        if total_trades == 0:
            return 0.0
        return self.winning_trades / total_trades * 100
    
    def update_deposit(self, amount: float, commission: float = 0.0):
        """
        Обновить депозит после закрытия позиции
        
        Args:
            amount: Изменение депозита (+прибыль, -убыток)
            commission: Комиссия по сделке
        """
        old_deposit = self.current_deposit
        
        # Учитываем комиссию
        self.total_commissions += commission
        total_change = amount - commission
        
        # Обновляем депозит
        self.current_deposit += total_change
        self.available_deposit += total_change
        
        # Обновляем дневной PnL
        self.daily_pnl += total_change
        self.total_pnl += total_change
        
        # Обновляем статистику сделок
        if total_change > 0:
            self.winning_trades += 1
        elif total_change < 0:
            self.losing_trades += 1
        
        # Обновляем сегодняшнюю запись
        if self.stats_history:
            today_stat = self.stats_history[-1]
            today_stat.current_deposit = self.current_deposit
            today_stat.daily_pnl = self.daily_pnl
            today_stat.total_pnl = self.total_pnl
            today_stat.total_commissions = self.total_commissions
            today_stat.closed_positions = self.closed_positions_count
            today_stat.win_rate = self.win_rate
        
        log.info(f"💳 Обновлен депозит: {old_deposit:.2f}₽ → {self.current_deposit:.2f}₽ "
                f"({'+' if total_change >= 0 else ''}{total_change:.2f}₽)")
    
    def block_funds(self, amount: float):
        """
        Заблокировать средства для открытия позиции
        
        Args:
            amount: Сумма для блокировки
        """
        if amount > self.available_deposit:
            raise ValueError(f"Недостаточно средств. Доступно: {self.available_deposit:.2f}₽, "
                           f"требуется: {amount:.2f}₽")
        
        self.available_deposit -= amount
        self.blocked_deposit += amount
        self.open_positions_count += 1
        
        # Обновляем статистику
        if self.stats_history:
            today_stat = self.stats_history[-1]
            today_stat.open_positions = self.open_positions_count
    
    def release_funds(self, amount: float):
        """
        Разблокировать средства после закрытия позиции
        
        Args:
            amount: Сумма для разблокировки
        """
        self.blocked_deposit -= amount
        self.closed_positions_count += 1
        self.open_positions_count -= 1
        
        # Обновляем статистику
        if self.stats_history:
            today_stat = self.stats_history[-1]
            today_stat.open_positions = self.open_positions_count
            today_stat.closed_positions = self.closed_positions_count
    
    def add_vm_accrual(self, amount: float):
        """
        Добавить начисление вариационной маржи
        
        Args:
            amount: Сумма ВМ (+прибыль, -убыток)
        """
        self.vm_accruals += amount
        self.current_deposit += amount
        self.available_deposit += amount
        
        # Обновляем статистику
        if self.stats_history:
            today_stat = self.stats_history[-1]
            today_stat.vm_accruals = self.vm_accruals
            today_stat.current_deposit = self.current_deposit
        
        log.info(f"📊 Начислена ВМ: {amount:+.2f}₽. Депозит: {self.current_deposit:.2f}₽")
    
    def get_max_position_size(self, leverage: float = 1.0) -> float:
        """
        Рассчитать максимальный размер позиции с учетом плеча
        
        Args:
            leverage: Плечо (5x-10x)
            
        Returns:
            Максимальная сумма для позиции
        """
        max_leverage = min(leverage, settings.MAX_LEVERAGE)
        max_leverage = max(max_leverage, settings.MIN_LEVERAGE)
        
        # Используем доступный депозит
        max_size = self.available_deposit * max_leverage
        
        # Для высокого риска можно использовать весь депозит
        if settings.RISK_LEVEL == 'high':
            max_size = self.current_deposit * max_leverage
        
        log.debug(f"Макс. размер позиции: {max_size:.2f}₽ (плечо {max_leverage}x)")
        return max_size
    
    def get_stats(self) -> Dict:
        """Получить текущую статистику портфеля"""
        return {
            'current_deposit': self.current_deposit,
            'available_deposit': self.available_deposit,
            'blocked_deposit': self.blocked_deposit,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'total_commissions': self.total_commissions,
            'vm_accruals': self.vm_accruals,
            'open_positions': self.open_positions_count,
            'closed_positions': self.closed_positions_count,
            'win_rate': self.win_rate,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_trades': self.winning_trades + self.losing_trades
        }
    
    def print_daily_report(self):
        """Напечатать дневной отчет"""
        stats = self.get_stats()
        
        print("\n" + "=" * 60)
        print("📊 ДНЕВНОЙ ОТЧЕТ ПОРТФЕЛЯ")
        print("=" * 60)
        print(f"Дата: {date.today().isoformat()}")
        print(f"Начальный депозит: {self.initial_deposit:.2f}₽")
        print(f"Текущий депозит: {stats['current_deposit']:.2f}₽")
        print(f"Доступно для торговли: {stats['available_deposit']:.2f}₽")
        print(f"Заблокировано: {stats['blocked_deposit']:.2f}₽")
        print(f"Дневной PnL: {stats['daily_pnl']:+.2f}₽")
        print(f"Общий PnL: {stats['total_pnl']:+.2f}₽")
        print(f"Комиссии: {stats['total_commissions']:.2f}₽")
        print(f"Вариационная маржа: {stats['vm_accruals']:+.2f}₽")
        print(f"Открыто позиций: {stats['open_positions']}")
        print(f"Закрыто позиций: {stats['closed_positions']}")
        print(f"Винрейт: {stats['win_rate']:.1f}%")
        print(f"Прибыльных/убыточных: {stats['winning_trades']}/{stats['losing_trades']}")
        print("=" * 60)


# Глобальный экземпляр
portfolio_manager = PortfolioManager()