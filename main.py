import time
import logging
import os
from pygase import Server, GameStateStore


logging.basicConfig(level=logging.DEBUG)

class GameServer(Server):
    def __init__(self):
        game_state_store = GameStateStore()
        game_state_store.game_state = {
            'players': {},
            'boxes': {str(i): {'x': 100 + i * 50, 'y': 100 + i * 30, 'hp': 3} for i in range(10)},
            'bullets': {}
        }
        print(f"Инициализированы бочки: {game_state_store.game_state['boxes']}")
        super().__init__(game_state_store)
        self.last_update = time.time() * 1000

        self._universal_event_handler.register_event_handler("MOVE", self.handle_move)
        self._universal_event_handler.register_event_handler("SHOOT", self.handle_shoot)
        self._universal_event_handler.register_event_handler("PICKUP", self.handle_pickup)

    def Connected(self, channel, addr):
        with self.game_state_store.access() as game_state:
            game_state['players'][str(channel)] = {'x': 400, 'y': 200, 'has_gun': False}
        print(f"Новый игрок подключился: {addr}, players: {game_state['players']}")
        self.SendToAll({'type': 'update', 'game_state': self.game_state_store.game_state})
        print("Отправлено начальное обновление всем клиентам")

    def handle_move(self, event, channel):
        x = event.handler_kwargs.get('x')
        y = event.handler_kwargs.get('y')
        with self.game_state_store.access() as game_state:
            game_state['players'][str(channel)]['x'] = x
            game_state['players'][str(channel)]['y'] = y
        print(f"Обработано событие MOVE для {channel}: x={x}, y={y}")
        self.SendToAll({'type': 'update', 'game_state': self.game_state_store.game_state})
        print("Отправлено обновление после MOVE")

    def handle_shoot(self, event, channel):
        dx = event.handler_kwargs.get('dx')
        dy = event.handler_kwargs.get('dy')
        with self.game_state_store.access() as game_state:
            bullet_id = str(len(game_state['bullets']))
            game_state['bullets'][bullet_id] = {
                'x': game_state['players'][str(channel)]['x'],
                'y': game_state['players'][str(channel)]['y'],
                'dx': dx,
                'dy': dy,
                'life': 200
            }
            print(f"Выстрел: bullet {bullet_id} добавлен на {game_state['bullets'][bullet_id]}")
        self.SendToAll({'type': 'bullet', 'game_state': self.game_state_store.game_state})
        print("Отправлено обновление после SHOOT")

    def handle_pickup(self, event, channel):
        with self.game_state_store.access() as game_state:
            game_state['players'][str(channel)]['has_gun'] = True
        print(f"Обработано событие PICKUP для {channel}")
        self.SendToAll({'type': 'update', 'game_state': self.game_state_store.game_state})
        print("Отправлено обновление после PICKUP")

    def Update(self):
        current_time = time.time() * 1000
        if current_time - self.last_update > 100:
            with self.game_state_store.access() as game_state:
                for bid in list(game_state['bullets'].keys()):
                    bullet = game_state['bullets'][bid]
                    bullet['x'] += bullet['dx']
                    bullet['y'] += bullet['dy']
                    bullet['life'] -= 1
                    if (bullet['x'] < 0 or bullet['x'] > 800 or bullet['y'] < 0 or bullet['y'] > 400 or bullet['life'] <= 0):
                        del game_state['bullets'][bid]
                        print(f"Пуля {bid} удалена (вышла за границы или истёк срок жизни)")
                        continue
                    for box_id, box in list(game_state['boxes'].items()):
                        if (abs(bullet['x'] - box['x']) < 20 and abs(bullet['y'] - box['y']) < 20):
                            box['hp'] -= 1
                            if box['hp'] <= 0:
                                del game_state['boxes'][box_id]
                                print(f"Бочка {box_id} уничтожена")
                            del game_state['bullets'][bid]
                            print(f"Пуля {bid} удалила бочку {box_id}")
                            break
            print(f"Отправка обновления: players={len(game_state['players'])}, boxes={len(game_state['boxes'])}, bullets={len(game_state['bullets'])}")
            self.SendToAll({'type': 'update', 'game_state': self.game_state_store.game_state})
            print("Отправлено обновление из Update")
            self.last_update = current_time

if __name__ == '__main__':
    server = GameServer()
    port  = int(os.environ.get("PORT", 12345))
    try:
        print("Запускаем сервер на порту 12345")
        server.run(hostname='0.0.0.0', port=port)
    except AttributeError:
        print("Запускаем сервер в ручном цикле")
        while True:
            server.Loop()