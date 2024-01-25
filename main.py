import math
import time
import sqlite3
import sys
from threading import Thread

import requests
import aiohttp
import asyncio
from PyQt5 import QtCore  # TODO: delete this
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QHeaderView, QLabel, QTableWidgetItem

import uis_module

# Адрес API Eve Online поддерживаеваемый самими разработчиками
EVE_BASE_API = "https://esi.evetech.net/latest/"

# Id систем/станций основных торговых хабов
SYSTEMS = {
    "JITA": (10000002, 60003760),
    "AMARR": (10000043, 60008494),
    "RENS": (10000030, 60004588),
    "DODIXIE": (10000032, 60011866)
}

type_id_to_name = dict()
start_time = time.time()
tax_rate = 0.92
try:
    with open('type_id_to_name.txt', encoding='utf-8') as file:
        for i in file.readlines():
            try:
                type_id_to_name[int(i[:12].replace(" ", ''))] = i[12:].rstrip()
            except BaseException:
                pass
finally:
    file.close()


class MySettings(uis_module.Ui_Settings):
    def __init__(self, other):
        super().__init__()
        # uic.loadUi('settings.ui', self)
        self.min_reward.insert(str(other.min_reward))
        self.max_order.insert(str(other.max_deals))
        self.save_mode.setCheckState(other.save_mode)


class MyDialog(uis_module.Ui_Danger):
    def __init__(self):
        super().__init__()
        # uic.loadUi('dialog.ui', self)


class MyWidget(uis_module.Ui_MainWindow):
    # TODO: заменить методом
    reverse_systems = {
        60003760: "JITA",
        60008494: "AMARR",
        60004588: "RENS",
        60011866: "DODIXIE"
    }
    progressChanged = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()
        # uic.loadUi('design.ui', self)  # Загружаем дизайн
        self.deals = []

        # Настройки пользователя
        self.min_reward = 1000
        self.max_deals = 20
        self.save_mode = False

        # кнопка запускающая анализ, очищающая таблицу, открывающая настройки
        self.startButton.clicked.connect(self.run)
        self.resButton.clicked.connect(self.clear_table)
        self.pushButton.clicked.connect(self.open_setting)

        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tableWidget.setColumnWidth(0, 35)
        self.tableWidget.setColumnWidth(1, 200)
        self.labels = self.roflan.findChildren(QLabel)
        self.progressChanged.connect(self.progressBar.setValue)

    def open_setting(self):
        dlg = MySettings(self)
        if dlg.exec():
            self.min_reward = int(dlg.min_reward.text())
            self.max_deals = int(dlg.max_order.text())
            self.save_mode = dlg.save_mode.checkState()

    def progress_bar(self, progress: float, text: str):
        if not self.save_mode:
            self.progressChanged.emit(math.floor(100 * progress))
            self.hintLabel.setText(text + "...")

    @staticmethod
    def number_to_money(num):
        if num > 1_000_000:
            return str(round(num / 1_000_000, 2)) + "m"
        elif num > 1_000:
            return str(round(num / 1_000, 2)) + "k"
        else:
            return str(num)

    def clear_table(self):
        for i in range(self.tableWidget.rowCount(), -1, -1):
            self.tableWidget.removeCellWidget(i, 0)
            self.tableWidget.removeRow(i)
        self.labels = self.roflan.findChildren(QLabel)

    def draw_table(self, deals):
        self.clear_table()
        self.deals = deals
        for i in range(0, min(len(self.deals), len(self.labels), self.max_deals) - 1):
            row_position = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row_position)
            self.tableWidget.setItem(row_position, 1, QTableWidgetItem(str(self.deals[i][1])))
            self.tableWidget.setItem(row_position, 2, QTableWidgetItem(self.number_to_money(self.deals[i][2])))
            self.tableWidget.setItem(row_position, 3, QTableWidgetItem(self.number_to_money(self.deals[i][3])))
            self.tableWidget.setItem(row_position, 4, QTableWidgetItem(str(self.deals[i][4])))
            self.tableWidget.setItem(row_position, 5, QTableWidgetItem(self.number_to_money(self.deals[i][5])))
            self.tableWidget.setItem(row_position, 6, QTableWidgetItem(str(self.deals[i][6])))
            self.tableWidget.setItem(row_position, 7, QTableWidgetItem(str(self.deals[i][7])))
        if not self.save_mode:
            self.progress_bar(0.95, "Загружаю картинки")
            for i in range(0, min(len(self.deals), len(self.labels), self.max_deals) - 1):
                image = QImage()
                image.loadFromData(requests.get(self.deals[i][0]).content)
                image_label = self.labels[i]
                image_label.setPixmap(QPixmap(image))
                self.tableWidget.setCellWidget(i, 0, image_label)
        # self.progressBar.reset()
        self.startButton.setEnabled(True)
        self.progress_bar(1, "Успешно! Спасибо за использование!")

    def run(self):
        if self.all_1.isChecked() is True and self.all_2.isChecked() is True:
            dlg = MyDialog()
            if not dlg.exec():
                return 0
        self.startButton.setEnabled(False)
        self.clear_table()
        thread = Thread(target=self.calculate_trades)
        thread.start()

    def calculate_trades(self):
        end_stations = []
        if self.all_1.isChecked() is True:
            end_stations = [*SYSTEMS.values()]
        else:
            if self.jita_1.isChecked() is True:
                end_stations.append(SYSTEMS["JITA"])
            elif self.rens_1.isChecked() is True:
                end_stations.append(SYSTEMS["RENS"])
            elif self.amarr_1.isChecked() is True:
                end_stations.append(SYSTEMS["AMARR"])
            elif self.dodixie_1.isChecked() is True:
                end_stations.append(SYSTEMS["DODIXIE"])
            else:
                self.hintLabel.setText("Некоректный маршрут")
                self.startButton.setEnabled(True)
                return 0
        start_stations = []
        if self.all_2.isChecked() is True:
            start_stations = [*SYSTEMS.values()]
        else:
            if self.jita_2.isChecked() is True:
                start_stations.append(SYSTEMS["JITA"])
            elif self.rens_2.isChecked() is True:
                start_stations.append(SYSTEMS["RENS"])
            elif self.amarr_2.isChecked() is True:
                start_stations.append(SYSTEMS["AMARR"])
            elif self.dodixie_2.isChecked() is True:
                start_stations.append(SYSTEMS["DODIXIE"])
            else:
                self.hintLabel.setText("Некоректный маршрут")
                self.startButton.setEnabled(True)
                return 0

        con = sqlite3.connect("data_base.db")
        cur = con.cursor()

        self.progress_bar(0, "Получаю type_id откуда")
        start_ids = asyncio.run(get_tradable_type_ids(start_stations[0][0]))
        self.progress_bar(0.02, "Получаю type_id куда")
        end_ids = asyncio.run(get_tradable_type_ids(end_stations[0][0]))
        both_trade_ids = start_ids.intersection(end_ids)
        self.progress_bar(0.04, "Очищаю базу данных")
        cur.execute("CREATE TABLE IF NOT EXISTS orders_from(type_id INTEGER, price REAL,"
                    " volume_remain INTEGER, location INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS orders_to(type_id INTEGER, price REAL,"
                    "volume_remain INTEGER, location INTEGER)")
        cur.execute("DELETE FROM orders_from")
        cur.execute("DELETE FROM orders_to")
        self.progress_bar(0.05, f"Получаю лоты откуда ({0}/{len(start_stations)})")
        orders_from = []
        prog = 0.05
        temp = (15 // len(start_stations)) * 0.01
        for i in range(len(start_stations)):
            orders_from.extend(asyncio.run(get_orders_by_type_ids(both_trade_ids, start_stations[i], 0)))
            self.progress_bar(prog + temp, f"Получаю лоты откуда ({i + 1}/{len(start_stations)})")
            prog += temp
        self.progress_bar(0.2, f"Получаю лоты куда ({0}/{len(end_stations)})")
        orders_to = []
        prog = 0.2
        temp = (15 // len(start_stations)) * 0.01
        for i in range(len(end_stations)):
            orders_to.extend(asyncio.run(get_orders_by_type_ids(both_trade_ids, end_stations[i], 1)))
            self.progress_bar(prog + temp, f"Получаю лоты куда ({i + 1}/{len(end_stations)})")
            prog += temp
        self.progress_bar(0.45, "Обновляю БД")
        for i in orders_from:
            for j in i:
                cur.execute(f"INSERT INTO orders_from VALUES ({j['type_id']}, {j['price']},"
                            f" {j['volume_remain']}, {j['location_id']})")
        for i in orders_to:
            for j in i:
                cur.execute(f"INSERT INTO orders_to VALUES ({j['type_id']}, {j['price']},"
                            f" {j['volume_remain']}, {j['location_id']})")

        self.progress_bar(0.5, "Загружаю данные из БД")
        all_orders = dict()
        cur.execute('SELECT * FROM orders_from')
        orders_from = cur.fetchall()
        cur.execute('SELECT * FROM orders_to')
        orders_to = cur.fetchall()
        for i in orders_from:
            if all_orders.get(i[0]) is None:
                all_orders[i[0]] = ([], [])
            all_orders[i[0]][0].append(Order(*i))
        for i in orders_to:
            if all_orders.get(i[0]) is None:
                all_orders[i[0]] = ([], [])
            all_orders[i[0]][1].append(Order(*i))

        del_list = []
        for i in all_orders:
            if len(all_orders[i][0]) == 0 or len(all_orders[i][1]) == 0:
                del_list.append(i)
        for i in del_list:
            del all_orders[i]
        self.progress_bar(0.6, "Вычисляю потенциально прибыльные сделки")
        unsorted_deals = []
        temp = 0
        counter = 0
        max_count = len(all_orders.keys())
        for key in all_orders.keys():
            counter += 1
            if temp == 100:
                pass
                self.hintLabel.setText(f"Вычисляю потенциально прибыльные сделки ({counter}/{max_count})")
                temp = 0
            else:
                temp += 1
            lowest_price_from = min(all_orders[key][0], key=lambda x: x.price)
            highest_price_to = max(all_orders[key][1], key=lambda x: x.price)
            maximum_items = min(lowest_price_from.volume_remain, highest_price_to.volume_remain)
            if highest_price_to.price * tax_rate > lowest_price_from.price:
                if type_id_to_name.get(key) is not None:
                    named = type_id_to_name[key]
                else:
                    named = requests.get(f"{EVE_BASE_API}universe/types/{key}").json()["name"]
                unsorted_deals.append((f"https://imageserver.eveonline.com/Type/{key}_32.png",
                                       named,
                                       lowest_price_from.price,
                                       highest_price_to.price,
                                       maximum_items,
                                       round(highest_price_to.price * tax_rate - lowest_price_from.price) \
                                       * maximum_items,
                                       self.reverse_systems[lowest_price_from.location],
                                       self.reverse_systems[highest_price_to.location]
                                       ))
        self.progress_bar(0.75, "Сортирую сделки")
        sorted_deals = sorted(unsorted_deals, key=lambda x: x[5], reverse=True)
        # Удаляем сделки которые меньше минимального порога выгодности
        temp = []
        for i in sorted_deals:
            if i[5] < self.min_reward:
                temp.append(i)
        for i in temp:
            sorted_deals.remove(i)
        self.progress_bar(0.8, "Печатаю таблицу")
        self.draw_table(sorted_deals)
        con.commit()
        con.close()


class Order:
    def __init__(self, type_id: int, price: float, volume_remain: int, location: int):
        self.price = price
        self.type_id = type_id
        self.volume_remain = volume_remain
        self.location = location

    def __repr__(self):
        return f"price: {self.price}, type_id: {self.type_id}, remain: {self.volume_remain}"

    def __str__(self):
        return f"price: {self.price}, type_id: {self.type_id}, remain: {self.volume_remain}"


async def get_resp(session, url):
    async with session.get(url) as resp:
        try:
            ans = await resp.json()
            return ans
        except BaseException:
            return None


async def get_tradable_type_ids(region: int) -> [int]:
    async with aiohttp.ClientSession() as session:

        tasks = []
        ans = set()
        last_page = int(requests.get(f"https://esi.evetech.net/latest/markets/{region}/types").headers['X-Pages'])

        for page in range(1, last_page):
            url = f'https://esi.evetech.net/latest/markets/{region}/types?page={page}'
            tasks.append(asyncio.ensure_future(get_resp(session, url)))

        id_lists = await asyncio.gather(*tasks)
        for id_list in id_lists:
            if id_list is not None:
                ans.update(id_list)
        return ans


async def get_orders_by_type_ids(type_ids: [int], location: (int, int), is_buy: int):
    async with aiohttp.ClientSession() as session:

        tasks = []

        for i in type_ids:
            url = f'https://esi.evetech.net/latest/markets/{location[0]}/orders?type_id={i}'
            tasks.append(asyncio.ensure_future(get_resp(session, url)))

        orders_unsorted = await asyncio.gather(*tasks)
        orders_sorted = []
        if is_buy == 2:
            pass
        else:
            for orders in orders_unsorted:
                if orders is not None:
                    ans = []
                    for t_order in orders:
                        if type(t_order) == dict and t_order["location_id"] == location[1] and bool(is_buy) == \
                                t_order["is_buy_order"]:
                            ans.append(t_order)
                    if len(ans) != 0:
                        orders_sorted.append(tuple(ans))
        return orders_sorted


app = QApplication(sys.argv)
ex = MyWidget()
ex.show()
sys.exit(app.exec_())
