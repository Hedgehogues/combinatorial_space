from copy import deepcopy
from enum import Enum

import Levenshtein
import numpy as np

from src.combinatorial_space.expetions import CombSpaceExceptions
from src.combinatorial_space.point import Point, PointPredictAnswer


class PREDICT_ENUM(Enum):
    THERE_ARE_NOT_AN_ACTIVE_POINTS = 0
    THERE_ARE_A_NONACTIVE_POINTS = 1
    ACCEPT = 2


class LEARN_ENUM(Enum):
    LEARN = 0
    SLEEP = 1


class Minicolumn:
    """
        Миниколонка. Миниколонка - это набор точек комбинаторного пространства

        space_size - количество точек комбинаторного пространства
        max_cluster_per_point - максимальное количество кластеров в точке
        max_count_clusters - максмальное суммарное количество кластеров по всем точкам комбинаторного пространства
        in_threshold_modify, out_threshold_modify - порог активации кластера. Если скалярное произведение базового
        вектора кластера на новый вектор больше порога, то будет пересчитан веса кластера, выделяющие первую главную
        компоненту
        threshold_bin - порог бинаризации кода
        in_threshold_activate, out_threshold_activate - порог активации точки комбинаторного пространства. Если кол-во
        активных битов больше порога, то будет инициирован процесс модификации существующих кластеров, а также будет
        добавлен новый кластер
        in_random_bits, out_random_bits - количество случайных битов входного/выходного вектора
        base_lr - начальное значение скорости обучения
        is_modify_lr - модификация скорости обучения пропорционально номер шага
        count_in_demensions, count_out_demensions - размер входного и выходного векторов
        threshold_controversy - порог противоречия для битов кодов
        code_aligment_threshold - число ненулевых бит в выходном векторе
    """
    def __init__(self, space_size=10000, max_cluster_per_point=100,
                 max_count_clusters=1000000, seed=42,
                 in_threshold_modify=5, out_threshold_modify=0,
                 in_threshold_activate=5, out_threshold_activate=0,
                 threshold_bin=0.1,
                 in_random_bits=24, out_random_bits=10,
                 base_lr=0.01, is_modify_lr=True,
                 count_in_demensions=256, count_out_demensions=16,
                 threshold_controversy=0.1,
                 code_aligment_threshold=6, count_active_point=30, class_point=Point):

        if seed is None or \
                space_size is None or in_threshold_modify is None or out_threshold_modify is None or \
                in_threshold_activate is None or out_threshold_activate is None or \
                in_random_bits is None or out_random_bits is None or \
                threshold_bin is None or is_modify_lr is None or \
                base_lr is None or max_cluster_per_point is None or \
                count_in_demensions is None or count_out_demensions is None or \
                max_count_clusters is None or threshold_controversy is None or \
                code_aligment_threshold is None or class_point is None or \
                count_active_point is None or count_active_point < 0 or \
                max_count_clusters <= 0 or space_size <= 0 or \
                in_random_bits > count_in_demensions or out_random_bits > count_out_demensions or \
                max_cluster_per_point < 0 or \
                out_random_bits < 0 or in_random_bits < 0 or \
                in_threshold_modify < 0 or out_threshold_modify < 0 or base_lr < 0 or \
                in_threshold_activate < 0 or out_threshold_activate < 0 or \
                count_in_demensions < 0 or count_out_demensions < 0 or \
                threshold_bin < 0 or type(is_modify_lr) is not bool or \
                threshold_controversy < 0 or code_aligment_threshold < 0 or \
                code_aligment_threshold > count_out_demensions or code_aligment_threshold > count_in_demensions:
                    raise ValueError("Неожиданное значение переменной")

        self.space = np.array(
            [
                class_point(
                    in_threshold_modify, out_threshold_modify,
                    in_threshold_activate, out_threshold_activate,
                    threshold_bin,
                    in_random_bits, out_random_bits,
                    count_in_demensions, count_out_demensions,
                    base_lr, is_modify_lr,
                    max_cluster_per_point
                ) for _ in range(space_size)
            ]
        )
        self.count_clusters = 0
        self.max_count_clusters = max_count_clusters
        self.count_in_demensions, self.count_out_demensions = count_in_demensions, count_out_demensions
        self.threshold_controversy = threshold_controversy
        self.code_aligment_threshold = code_aligment_threshold
        self.count_active_point = count_active_point

        self.__threshold_active = None
        self.__threshold_in_len = None
        self.__threshold_out_len = None
        self.__clusters_of_points = None
        self.__active_clusters = None

        self.out_fail = None
        self.in_fail = None
        self.in_not_detected = None
        self.out_not_detected = None
        self.zeros_detected = None
        
        np.random.seed(seed)

    def __predict_prepare_code(self, code, count):
        controversy = np.sum(np.uint8(np.abs(np.divide(code[count != 0], count[count != 0])) < self.threshold_controversy))
        code[code <= 0] = 0
        code[code > 0] = 1

        return controversy

    def __predict(self, code, count_demensions_0, count_demensions_1, is_front):
        CombSpaceExceptions.none(code, 'Не определён входной аргумент')
        CombSpaceExceptions.len(len(code), count_demensions_0, 'Не совпадает размерность')
        CombSpaceExceptions.code_value(code)

        pred_code = [0] * count_demensions_1
        count = np.array([0] * count_demensions_1)
        # TODO: отдавать статистику
        not_active = 0
        no_clusters = 0
        active = 0
        for point in self.space:
            if is_front:
                pred_code_local, status = point.predict_front(code)
            else:
                pred_code_local, status = point.predict_back(code)

            if status == PointPredictAnswer.NOT_ACTIVE:
                not_active += 1
                continue
            elif status == PointPredictAnswer.NO_CLUSTERS:
                no_clusters += 1
                continue
            elif status == PointPredictAnswer.ACTIVE:
                active += 1

            CombSpaceExceptions.none(pred_code_local, 'Не определён входной аргумент')
            CombSpaceExceptions.len(len(pred_code_local), count_demensions_1, 'Не совпадает размерность')

            count += np.uint8(pred_code_local != 0)
            pred_code += pred_code_local

        if active != len(self.space):
            if active == 0:
                return None, None, PREDICT_ENUM.THERE_ARE_NOT_AN_ACTIVE_POINTS
            else:
                # TODO: количество активных кластеров может быть очень маленьким. Если кластеров мало, то, вероятно, они неинформативные
                controversy = self.__predict_prepare_code(pred_code, count)
                return controversy, pred_code, PREDICT_ENUM.THERE_ARE_A_NONACTIVE_POINTS

        controversy = self.__predict_prepare_code(pred_code, count)
        return controversy, pred_code, PREDICT_ENUM.ACCEPT

    """
        Получение выходного кода по входному. Прямое предсказание в каждой точке комбинаторного пространства
        
        in_code - входной код
        
        Возвращаемые значения: непротиворечивость, выходной код. В случае отсутствия хотя бы одной активной точки,
        возвращается бесконечное значение противоречивости
    """
    def front_predict(self, in_code):
        return self.__predict(in_code, self.count_in_demensions, self.count_out_demensions, True)
    
    """
        Получение входного кода по выходному. Обратное предсказание в каждой точке комбинаторного пространства
        
        out_code - выходной код
        
        Возвращаемые значения: непротиворечивость, входной код
    """
    def back_predict(self, out_code):
        return self.__predict(out_code, self.count_out_demensions, self.count_in_demensions, False)

    def __sleep_process_clusters(self, point):

        for cluster_ind, cluster in enumerate(point.clusters):
            in_active_mask = np.abs(cluster.in_w) > self.__threshold_active
            out_active_mask = np.abs(cluster.out_w) > self.__threshold_active

            if len(cluster.in_w[in_active_mask]) > self.__threshold_in_len and \
                            len(cluster.out_w[out_active_mask]) > self.__threshold_out_len:

                # Подрезаем кластер
                cluster.in_w[~in_active_mask] = 0
                cluster.out_w[~out_active_mask] = 0

                self.__active_clusters.append(cluster)
                self.__clusters_of_points[-1].append(cluster_ind)
            else:
                self.count_clusters -= 1

    def __sleep_remove_the_same_clusters(self, point):

        # Удаляем одинаковые кластеры (те кластеры, у которых одинаковые базовые векторы)
        the_same_clusters = 0
        point.clusters = []
        for cluster_i in range(len(self.__active_clusters)):
            is_exist_the_same = False
            for cluster_j in range(cluster_i + 1, len(self.__active_clusters)):
                if np.sum(np.uint8(self.__active_clusters[cluster_i].in_w == \
                   self.__active_clusters[cluster_j].in_w)) == len(self.__active_clusters[cluster_i].in_w) \
                        and \
                   np.sum(np.uint8(self.__active_clusters[cluster_i].out_w == \
                   self.__active_clusters[cluster_j].out_w)) == len(self.__active_clusters[cluster_i].out_w):
                    is_exist_the_same = True
                    continue
            if not is_exist_the_same:
                point.clusters.append(self.__active_clusters[cluster_i])
            else:
                the_same_clusters += 1
                self.count_clusters -= 1
        return the_same_clusters

    """
        Этап сна
        
        threshold_active - порог активности бита внутри кластера (вес в преобразовании к первой главной компоненте), 
        выше которого активность остаётся
        threshold_in_len, threshold_out_len - порог количества ненулевых битов
        
        Возвращается количество одинаковых кластеров
    """    
    def sleep(self, threshold_active=0.75, threshold_in_len=4, threshold_out_len=0):
        CombSpaceExceptions.none(threshold_active, 'Не определён аргумент')
        CombSpaceExceptions.none(threshold_in_len, 'Не определён аргумент')
        CombSpaceExceptions.none(threshold_out_len, 'Не определён аргумент')
        CombSpaceExceptions.less(threshold_active, 0, 'Недопустимое значение аргумента')
        CombSpaceExceptions.more(threshold_active, 1, 'Недопустимое значение аргумента')
        CombSpaceExceptions.less(threshold_in_len, 0, 'Недопустимое значение аргумента')
        CombSpaceExceptions.less(threshold_out_len, 0, 'Недопустимое значение аргумента')

        the_same_clusters = 0

        self.__threshold_active = threshold_active
        self.__threshold_in_len = threshold_in_len
        self.__threshold_out_len = threshold_out_len
        self.__clusters_of_points = []

        for point_ind, point in enumerate(self.space):
            self.__clusters_of_points.append([])
            self.__active_clusters = []

            # Отбор наиболее информативных кластеров
            self.__sleep_process_clusters(point)
                    
            # Удаляем одинаковые кластеры (те кластеры, у которых одинаковые базовые векторы)
            the_same_clusters += self.__sleep_remove_the_same_clusters(point)
            
        return self.__clusters_of_points, the_same_clusters
        
    """
        Проверям: пора ли спать
    """
    def is_sleep(self):
        return self.count_clusters > self.max_count_clusters
    
    def __code_alignment(self, code):
        count_active_bits = np.sum(code)
        if count_active_bits > self.code_aligment_threshold:
            active_bits = np.where(code == 1)[0]
            count_active_bits = active_bits.shape[0]
            stay_numbers = np.random.choice(
                count_active_bits, self.code_aligment_threshold, replace=False
            )
            active_bits = active_bits[stay_numbers]
            code_mod = np.zeros(code.shape[0])
            code_mod[active_bits] = 1
        elif count_active_bits < self.code_aligment_threshold:
            non_active_bits = np.where(code == 0)[0]
            count_non_active_bits = non_active_bits.shape[0]
            count_active_bits = code.shape[0] - count_non_active_bits
            stay_numbers = np.random.choice(
                count_non_active_bits, self.code_aligment_threshold - count_active_bits, replace=False
            )
            non_active_bits = non_active_bits[stay_numbers]
            code_mod = deepcopy(code)
            code_mod[non_active_bits] = 1
        else:
            code_mod = deepcopy(code)
        return np.int8(code_mod)

    """
        Статистика по обработке последней группы кодов
        
        Количество противоречивых выходных и входных кодов;
        количество входных и выходных кодов, которых нет в памяти  
    """
    def get_stat(self):
        return self.out_fail, self.in_fail, self.in_not_detected, self.out_not_detected, self.zeros_detected

    """
        Этап обучения без учителя (не написан один тест. см. тесты)
        
        Делается предсказание для всех переданных кодов и выбирается самый непротиворечивый из них, 
        либо констатируется, что такого нет.
        
        Для каждой активной точки выбирается наиболее подходящий кластер. Его предсказание учитывается в качестве
        ответа. Для конкретной точки все остальные кластеры учтены не будут.
        
        В качестве результата непротиворечивости берём среднее значение по ответам делёное на число активных точек.
        
        Замечание: в случае, если кода нет в памяти, то генерируется случайный код. В таком случае,
                   вызов данной функции будет не воспроизводимым.  
        
        in_codes - входные коды в разных контекстах
        threshold_controversy_in, threshold_controversy_out - порого противоречивости для кодов
        
        Возвращается оптимальный код, порядковый номер контекста-победителя
    """
    def unsupervised_learning(self, in_codes, threshold_controversy_in=3, threshold_controversy_out=3):

        CombSpaceExceptions.codes(in_codes, self.count_in_demensions)
        CombSpaceExceptions.none(threshold_controversy_in, 'Неопределён аргумент')
        CombSpaceExceptions.none(threshold_controversy_out, 'Неопределён аргумент')
        CombSpaceExceptions.less(threshold_controversy_in, 'Недопустимое значение переменной')
        CombSpaceExceptions.less(threshold_controversy_out, 'Недопустимое значение переменной')

        min_hamming = np.inf
        min_ind_hamming = None
        min_out_code = None
        self.out_fail = 0
        self.in_fail = 0
        self.in_not_detected = 0
        self.out_not_detected = 0
        self.zeros_detected = 0
        for index in range(len(in_codes)):

            # Не обрабатываются полностью нулевые коды
            if np.sum(in_codes[index]) == 0:
                self.zeros_detected += 1
                continue

            # TODO: холодный старт. С чего начинать?
            # TODO: если ни один код не распознан (status всегда принимает значения не равные ACCEPT),
            # TODO: то создаём случайный выходной вектор для первого кода из всех входных
            #############
            # TODO: что делать, если в одном из контекстов мы не можем распознать ничего, а в других можем?
            # TODO: на данном этапе забиваем на такие коды
            #############
            controversy_out, out_code, status = self.front_predict(np.array(in_codes[index]))
            if status is not PREDICT_ENUM.ACCEPT:
                self.out_not_detected += 1
                continue

            # TODO: что если все коды противоречивые? как быть?
            # TODO: на данном этапе такой код не добавляем
            ############
            if controversy_out > threshold_controversy_out:
                self.out_fail += 1
                continue
                
            # Удаляем или добавляем единицы (если их мало или много)
            out_code = self.__code_alignment(out_code)
            
            controversy_in, in_code, status = self.back_predict(out_code)
            # TODO: при обратном предсказании не распознано, а при прямом -- распознано
            # TODO: на данном этапе забиваем на такие коды
            ############
            if status is not PREDICT_ENUM.ACCEPT:
                self.in_not_detected += 1
                continue
            
            if controversy_in > threshold_controversy_in:
                self.in_fail += 1
                continue

            hamming_dist = Levenshtein.hamming(''.join(map(str, in_code)), ''.join(map(str, in_codes[index])))
            if min_hamming > hamming_dist:
                min_hamming = hamming_dist
                min_ind_hamming = index
                min_out_code = out_code

        if self.zeros_detected != len(in_codes) and \
                self.in_not_detected + self.out_not_detected + self.zeros_detected == len(in_codes):
            # TODO: выбирается наиболее активный код (правильно ли это?)
            min_ind_hamming = 0
            max_ones = -1
            for ind, code in enumerate(in_codes):
                sum_ones = np.sum(code)
                if sum_ones > max_ones:
                    max_ones = sum_ones
                    min_ind_hamming = ind

            # Генерируем случайный код
            min_out_code = self.__code_alignment(np.array([0] * self.count_out_demensions))

        if min_out_code is not None:
            return in_codes[min_ind_hamming], min_out_code, min_ind_hamming
        else:
            return None, None, None
    
    """
        Этап обучения без учителя (функция не протестирована, так как очень похожа на unsupervised_learning)
        
        Делается предсказание для всех переданных кодов и выбирается самый непротиворечивый из них, 
        либо констатируется, что такого нет.
        
        Для каждой активной точки выбирается наиболее подходящий кластер. Его предсказание учитывается в качестве
        ответа. Для конкретной точки все остальные кластеры учтены не будут.
        
        В качестве результата непротиворечивости берём среднее значение по ответам делёное на число активных точек.
        
        codes - входные коды в разных контекстах
        threshold_controversy_in, threshold_controversy_out - порого противоречивости для кодов
        
        Возвращается минимальный индекс предсказанного кода в смысле хемминга
    """
    def supervised_learning(self, in_codes, out_codes, threshold_controversy_out=3):

        CombSpaceExceptions.codes(in_codes, self.count_in_demensions)
        CombSpaceExceptions.codes(out_codes, self.count_out_demensions)
        CombSpaceExceptions.none(threshold_controversy_out, 'Неопределён аргумент')
        CombSpaceExceptions.less(threshold_controversy_out, 'Недопустимое значение переменной')

        min_hamming = np.inf
        min_ind_hamming = None
        self.out_fail = 0
        self.in_fail = 0
        self.in_not_detected = 0
        self.out_not_detected = 0
        self.zeros_detected = 0
        for index in range(len(in_codes)):

            # Не обрабатываются полностью нулевые коды
            if np.sum(in_codes[index]) == 0:
                # TODO: zeros_detected не протестирован
                self.zeros_detected += 1
                continue

            # TODO: холодный старт. С чего начинать?
            # TODO: если ни один код не распознан (accept всегда принимает значения не равные ACCEPT),
            # TODO: то берём первый попавшийся код (например, нулевой по счёту)
            #############
            # TODO: что делать, если в одном из контекстов мы не можем распознать ничего, а в других можем?
            # TODO: на данном этапе забиваем на такие коды
            #############
            controversy_out, out_code, accept = self.front_predict(np.array(in_codes[index]))
            if accept is not PREDICT_ENUM.ACCEPT:
                self.out_not_detected += 1
                continue

            # TODO: что если все коды противоречивые? как быть?
            # TODO: на данном этапе такой код не добавляем
            ############
            if controversy_out > threshold_controversy_out:
                self.out_fail += 1
                continue                
            
            hamming_dist = Levenshtein.hamming(''.join(map(str, out_code)), ''.join(map(str, out_codes[index])))
            if min_hamming < hamming_dist:
                min_hamming = hamming_dist
                min_ind_hamming = index

        # Если ни один код не определился, то берём самый первый
        if self.zeros_detected != len(in_codes) and self.in_not_detected + self.out_not_detected + self.zeros_detected == len(in_codes):
            # TODO: выбирается наиболее активный код (правильно ли это?)
            min_ind_hamming = 0
            max_ones = -1
            for ind, code in enumerate(in_codes):
                sum_ones = np.sum(code)
                if sum_ones > max_ones:
                    max_ones = sum_ones
                    min_ind_hamming = ind

        if min_ind_hamming is not None:
            return in_codes[min_ind_hamming], out_codes[min_ind_hamming], min_ind_hamming
        else:
            return None, None, None
    
    
    """
        Этап обучения (не протестирована)
        
        Создание и модификация кластеров на основе пары кодов: входной и выходной
        
        in_code, out_code - входной и выходной коды
        threshold_controversy_in, threshold_controversy_out - пороги противоречивости на входной и выходной коды
        
        Возвращается количество точек, которые оказались неактивными; количество модификаций кластеров;
        количество новых кластеров
    """
    def learn(self, in_codes, out_codes=None, threshold_controversy_in=20, threshold_controversy_out=6):
        if self.is_sleep():
            return None, None, None, LEARN_ENUM.SLEEP

        count_fails = 0
        count_modify = 0
        count_adding = 0

        if out_codes is not None:
            in_code, out_code, opt_ind = self.supervised_learning(in_codes, out_codes, threshold_controversy_out)
        else:
            in_code, out_code, opt_ind = self.unsupervised_learning(
                in_codes, threshold_controversy_in, threshold_controversy_out
            )
        if in_code is not None:
            for point in self.space:
                local_count_fails, local_count_modify, local_count_adding = point.add(in_code, out_code)
                count_modify += local_count_modify
                count_fails += local_count_fails
                count_adding += local_count_adding
                self.count_clusters += local_count_adding
        return count_fails, count_modify, count_adding, LEARN_ENUM.LEARN