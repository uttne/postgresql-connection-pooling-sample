import psycopg2
from sqlalchemy.engine.url import URL
import threading
import time
import datetime as dt

user = "postgres"
password = "p@ssw0rd"
host = "localhost"
port = "15432"
portPool = "16432"
dbname = "postgres"

# @ マークのエスケープ
# https://qiita.com/takkeybook/items/e34afdba936f2062590e
connection_url = str(URL.create(
    drivername="postgresql",
    username=user,
    password=password,
    host=host,
    port=port,
    database=dbname
))

connection_pool_url = str(URL.create(
    drivername="postgresql",
    username=user,
    password=password,
    host=host,
    port=portPool,
    database=dbname
))


class SqlThread(threading.Thread):
    def __init__(self, connection_url: str) -> None:
        super().__init__()
        self.connection_url = connection_url
        self.request_result = ""

        self.pattern = 1
        self.repeat = 10

    def run_pattern_01(self):
        """
        セッションを都度閉じる
        セッション外でスリープする
        """
        self.request_result = ""

        try:
            for i in range(self.repeat):
                connector = psycopg2.connect(self.connection_url)

                with connector:
                    with connector.cursor() as cursor:
                        # 初回実行時にトランザクション開始
                        # それ以降がトランザクションを使いまわし
                        cursor.execute("SELECT 1;")
                        self.request_result += "o"
                # connector の with 終了でトランザクション終了

                # 最後に必ず閉じる
                connector.close()

                # セッションを閉じた後にスリープ
                time.sleep(1)
        except Exception:
            self.request_result += "X"

    def run_pattern_02(self):
        """
        セッションを都度閉じる
        セッション内でスリープする
        """
        self.request_result = ""

        try:
            for i in range(self.repeat):
                connector = psycopg2.connect(self.connection_url)

                with connector:
                    with connector.cursor() as cursor:
                        # 初回実行時にトランザクション開始
                        # それ以降がトランザクションを使いまわし
                        cursor.execute("SELECT 1;")
                        self.request_result += "o"

                # connector の with 終了でトランザクション終了

                # セッションを閉じる前にスリープ
                time.sleep(1)

                # 最後に必ず閉じる
                connector.close()

        except Exception:
            self.request_result += "X"

    def run_pattern_03(self):
        """
        セッションを都度閉じる
        トランザクション内でスリープする
        """
        self.request_result = ""

        try:
            for i in range(self.repeat):
                connector = psycopg2.connect(self.connection_url)

                with connector:
                    with connector.cursor() as cursor:
                        # 初回実行時にトランザクション開始
                        # それ以降がトランザクションを使いまわし
                        cursor.execute("SELECT 1;")
                        self.request_result += "o"

                    # トランザクション内でスリープ
                    time.sleep(1)

                # connector の with 終了でトランザクション終了

                # 最後に必ず閉じる
                connector.close()

        except Exception:
            self.request_result += "X"

    def run_pattern_04(self):
        """
        セッションを開けたまま
        トランザクション外でスリープする
        """
        self.request_result = ""

        try:
            connector = psycopg2.connect(self.connection_url)

            for i in range(self.repeat):
                with connector:
                    with connector.cursor() as cursor:
                        # 初回実行時にトランザクション開始
                        # それ以降がトランザクションを使いまわし
                        cursor.execute("SELECT 1;")
                        self.request_result += "o"
                # connector の with 終了でトランザクション終了

                # トランザクションの外でスリープ
                time.sleep(1)

            # 最後に必ず閉じる
            connector.close()
        except Exception:
            self.request_result += "X"

    def run_pattern_05(self):
        """
        セッションを開けたまま
        トランザクション内でスリープする
        """
        self.request_result = ""

        try:
            connector = psycopg2.connect(self.connection_url)

            for i in range(self.repeat):
                with connector:
                    with connector.cursor() as cursor:
                        # 初回実行時にトランザクション開始
                        # それ以降がトランザクションを使いまわし
                        cursor.execute("SELECT 1;")
                        self.request_result += "o"

                    # トランザクションの中でスリープ
                    time.sleep(1)

                # connector の with 終了でトランザクション終了

            # 最後に必ず閉じる
            connector.close()
        except Exception:
            self.request_result += "X"

    def run(self):

        run_pattern = [self.run_pattern_01, self.run_pattern_02,
                       self.run_pattern_03, self.run_pattern_04, self.run_pattern_05]

        run_pattern[self.pattern-1]()


class MeasureThread(threading.Thread):
    def __init__(self, connection_url: str, targets: list[SqlThread]) -> None:
        super().__init__()

        self.connection_url = connection_url
        self.targets = targets
        self.repeat = 10
        self.pattern = 1

        self.start_time: dt.datetime | None = None
        self.end_time: dt.datetime | None = None

    def stop(self):
        self.end_time = dt.datetime.now()

    def run(self):

        self.start_time = dt.datetime.now()

        connection_url = self.connection_url
        sql = "SELECT pid, backend_start, xact_start, query_start, state_change, state FROM pg_stat_activity WHERE state <> '';"
        connector = psycopg2.connect(connection_url)

        col = 5
        lines = ["" for _ in range(
            len(self.targets) // col + (1 if 0 < (len(self.targets) % col) else 0))]

        result_empty = "".join([" " for _ in range(self.repeat)])
        text_lines = lines + [""]
        print("\n".join(text_lines) + "\n")

        delay_count = 3
        while True:

            lines = ["" for _ in lines]
            for index, result in enumerate([target.request_result for target in self.targets]):
                i = index % len(lines)
                item = lines[i] + \
                    f"{('000' + str(index))[-3:]}: {(result+result_empty)[:len(result_empty)]} | "
                lines[i] = item

            with connector:
                with connector.cursor() as cursor:
                    cursor.execute(query=sql)
                    rows = cursor.fetchall()

            start_time = self.start_time
            end_time = self.end_time if self.end_time != None else dt.datetime.now()
            text_lines = lines + \
                [f"Pattern = {self.pattern} : Elapsed time = {end_time - start_time} : PostgreSQL session count = {len(rows) - 1}"]
            text = f"\033[{len(text_lines)}A" + "\n".join(text_lines) + "\n"
            print(text, end="")

            if self.end_time != None:
                if delay_count <= 0:
                    break
                delay_count -= 1

            time.sleep(1)

        connector.close()


# SQL の実行パターン
pattern = 2
# SQL の実行スレッド数
sql_thread_count = 120

# SQL の実行スレッドの用意
targets: list[SqlThread] = []
for i in range(sql_thread_count):
    t = SqlThread(connection_url=connection_pool_url)
    t.pattern = pattern
    targets.append(t)

# 計測スレッドの用意
measure_thread = MeasureThread(connection_url=connection_url, targets=targets)
measure_thread.pattern = pattern
measure_thread.start()

for t in targets:
    t.start()

for t in targets:
    t.join()

measure_thread.stop()
measure_thread.join()
