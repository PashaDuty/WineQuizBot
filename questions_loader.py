"""
Модуль загрузки и управления вопросами из JSON файлов
"""
import json
import os
import random
import logging
from typing import List, Dict, Optional
from config import QUESTIONS_PATH, COUNTRIES

logger = logging.getLogger(__name__)


class QuestionsManager:
    """Менеджер вопросов - загружает и кеширует вопросы из JSON"""
    
    def __init__(self):
        self._questions_cache: Dict[str, Dict[str, List[dict]]] = {}
        self._loaded = False
    
    async def load_all_questions(self):
        """Загрузить все вопросы из JSON файлов"""
        self._questions_cache = {}
        
        for country_code, country_data in COUNTRIES.items():
            self._questions_cache[country_code] = {}
            country_path = os.path.join(QUESTIONS_PATH, country_code.capitalize() 
                                        if country_code == "france" else country_code)
            
            # Проверяем альтернативные варианты названия папки
            if not os.path.exists(country_path):
                # Пробуем разные варианты
                for variant in [country_code, country_code.capitalize(), country_code.upper(), 
                               country_code.lower()]:
                    test_path = os.path.join(QUESTIONS_PATH, variant)
                    if os.path.exists(test_path):
                        country_path = test_path
                        break
            
            if not os.path.exists(country_path):
                logger.warning(f"[WARN] Papka strany ne najdena: {country_path}")
                continue
            
            for region_code, region_data in country_data["regions"].items():
                file_path = os.path.join(country_path, region_data["file"])
                
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            questions = json.load(f)
                            self._questions_cache[country_code][region_code] = questions
                            logger.info(f"[OK] Zagruzheno {len(questions)} voprosov: {country_code}/{region_code}")
                    except json.JSONDecodeError as e:
                        logger.error(f"[ERROR] Oshibka JSON v fajle {file_path}: {e}")
                    except Exception as e:
                        logger.error(f"[ERROR] Oshibka pri zagruzke {file_path}: {e}")
                else:
                    logger.warning(f"[WARN] Fajl ne najden: {file_path}")
        
        self._loaded = True
        logger.info("[DONE] Zagruzka voprosov zavershena!")
    
    def get_questions_for_region(self, country: str, region: str) -> List[dict]:
        """Получить вопросы для конкретного региона"""
        if country in self._questions_cache and region in self._questions_cache[country]:
            return self._questions_cache[country][region].copy()
        return []
    
    def get_questions_for_country(self, country: str) -> List[dict]:
        """Получить все вопросы для страны"""
        questions = []
        if country in self._questions_cache:
            for region_questions in self._questions_cache[country].values():
                questions.extend(region_questions)
        return questions
    
    def get_all_questions(self) -> List[dict]:
        """Получить все вопросы из всех стран"""
        questions = []
        for country_questions in self._questions_cache.values():
            for region_questions in country_questions.values():
                questions.extend(region_questions)
        return questions
    
    def get_random_questions(self, 
                             count: int, 
                             country: Optional[str] = None, 
                             region: Optional[str] = None) -> List[dict]:
        """
        Получить случайные вопросы
        
        Args:
            count: Количество вопросов
            country: Код страны (опционально)
            region: Код региона (опционально, требует country)
        
        Returns:
            Список случайных вопросов
        """
        # Определяем пул вопросов
        if country and region:
            pool = self.get_questions_for_region(country, region)
        elif country:
            pool = self.get_questions_for_country(country)
        else:
            pool = self.get_all_questions()
        
        # Если вопросов меньше, чем запрошено - берём все
        if len(pool) <= count:
            questions = pool.copy()
        else:
            questions = random.sample(pool, count)
        
        # Перемешиваем порядок
        random.shuffle(questions)
        return questions
    
    def get_questions_count(self, 
                           country: Optional[str] = None, 
                           region: Optional[str] = None) -> int:
        """Получить количество доступных вопросов"""
        if country and region:
            return len(self.get_questions_for_region(country, region))
        elif country:
            return len(self.get_questions_for_country(country))
        else:
            return len(self.get_all_questions())
    
    def get_available_regions(self, country: str) -> Dict[str, int]:
        """Получить доступные регионы и количество вопросов в них"""
        regions = {}
        if country in self._questions_cache:
            for region_code, questions in self._questions_cache[country].items():
                if questions:  # Только если есть вопросы
                    regions[region_code] = len(questions)
        return regions
    
    def get_available_countries(self) -> Dict[str, int]:
        """Получить доступные страны и количество вопросов в них"""
        countries = {}
        for country_code in self._questions_cache:
            count = self.get_questions_count(country=country_code)
            if count > 0:
                countries[country_code] = count
        return countries


# Глобальный экземпляр менеджера вопросов
questions_manager = QuestionsManager()
