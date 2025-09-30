from jesse.config import config
from jesse.models import Position
from jesse.models.PositionPair import PositionPair


class PositionsState:
    def __init__(self) -> None:
        self.storage = {}

        for exchange in config['app']['trading_exchanges']:
            for symbol in config['app']['trading_symbols']:
                key = f'{exchange}-{symbol}'
                
                # Check if this exchange is in hedge mode
                position_mode = config['env']['exchanges'][exchange].get('futures_position_mode', 'one-way')
                
                if position_mode == 'hedge':
                    # Create PositionPair for hedge mode
                    self.storage[key] = PositionPair(exchange, symbol)
                else:
                    # Create single Position for one-way mode (existing behavior)
                    self.storage[key] = Position(exchange, symbol)

    def count_open_positions(self) -> int:
        c = 0
        for key in self.storage:
            p = self.storage[key]
            
            # Handle both Position and PositionPair
            if isinstance(p, PositionPair):
                # In hedge mode, count if any position is open
                if p.has_any_open:
                    c += 1
            else:
                # One-way mode (existing behavior)
                if p.is_open:
                    c += 1
        return c
