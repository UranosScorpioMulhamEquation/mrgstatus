import datetime
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

import geonamescache
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder

# =============================================================================
# 1. إعدادات المحرك الفلكي (Swiss Ephemeris) وتنسيق واجهة Streamlit (RTL)
# =============================================================================
# ==========================================
# 0. تهيئة مسار ملفات الـ Ephemeris
# ==========================================
EPHE_PATH = "./ephe"
if not os.path.exists(EPHE_PATH):
    os.makedirs(EPHE_PATH)

swe.set_ephe_path(EPHE_PATH)

st.set_page_config(
    page_title="المحرك الفلكي المتقدم لتقييم قوى الكواكب وصلاحية الزواج",
    layout="wide",
    page_icon="🔭"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Amiri:wght@700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
        color: #ffffff;
        font-weight: 800;
        font-size: 17px;
        padding: 14px;
        border-radius: 10px;
        border: 1px solid #d4af37;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #d4af37 0%, #b48a1e 100%);
        color: #0f172a;
        border-color: #fde047;
        box-shadow: 0 4px 18px rgba(212, 175, 55, 0.45);
    }
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #090d16 0%, #172554 100%);
        color: #f8fafc;
        padding: 26px;
        border-radius: 14px;
        border: 2px solid #d4af37;
        margin-bottom: 25px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.12);
    }
    .main-header h1 {
        font-family: 'Amiri', serif;
        color: #facc15;
        font-size: 30px;
        margin-bottom: 8px;
        font-weight: 700;
    }
    .result-card {
        background: #ffffff;
        border-right: 6px solid #d4af37;
        border-radius: 10px;
        padding: 22px;
        margin-bottom: 20px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
    }
    .rec-box {
        background: #f8fafc;
        border-right: 5px solid #2563eb;
        padding: 18px;
        border-radius: 10px;
        margin-top: 15px;
        border: 1px solid #cbd5e1;
    }
    .planet-detail-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. وحدة البيانات الجغرافية والمناطق الزمنية الديناميكية
# =============================================================================
@dataclass
class City:
    geonameid: str
    name: str
    country_code: str
    latitude: float
    longitude: float
    admin1: str
    population: int

@st.cache_data
def load_geo_data():
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    raw_cities = gc.get_cities()

    country_map = {c["name"]: code for code, c in countries.items()}
    sorted_countries = sorted(list(country_map.keys()))

    cities_by_country: Dict[str, List[City]] = {code: [] for code in country_map.values()}
    for city_id, c_data in raw_cities.items():
        if c_data.get("population", 0) >= 15000:
            c_code = c_data.get("countrycode", "")
            if c_code in cities_by_country:
                cities_by_country[c_code].append(
                    City(
                        geonameid=city_id,
                        name=c_data.get("name", ""),
                        country_code=c_code,
                        latitude=float(c_data.get("latitude", 0.0)),
                        longitude=float(c_data.get("longitude", 0.0)),
                        admin1=c_data.get("admin1code", ""),
                        population=int(c_data.get("population", 0)),
                    )
                )

    for c_code in cities_by_country:
        cities_by_country[c_code].sort(key=lambda x: x.population, reverse=True)

    return country_map, sorted_countries, cities_by_country

country_map, country_list, cities_by_country = load_geo_data()
tf = TimezoneFinder()

# =============================================================================
# 3. المعاجم الفلكية الشاملة (الكواكب العشرة، الكرامات، الحدود، الكويكبات، النجوم)
# =============================================================================
ZODIAC_NAMES_AR = [
    "الحمل", "الثور", "الجوزاء", "السرطان",
    "الأسد", "العذراء", "الميزان", "العقرب",
    "القوس", "الجدي", "الدلو", "الحوت"
]

PERSONAL_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars"]

ALL_PLANETS_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

ALL_PLANETS_AR = {
    "Sun": "الشمس",
    "Moon": "القمر",
    "Mercury": "عطارد",
    "Venus": "الزهرة",
    "Mars": "المريخ",
    "Jupiter": "المشتري",
    "Saturn": "زحل",
    "Uranus": "أورانوس",
    "Neptune": "نبتون",
    "Pluto": "بلوتو"
}

# متوسط السرعة اليومية للكواكب الشخصية (درجة/يوم) لتقييم السرعة والبطء
AVERAGE_DAILY_SPEEDS = {
    "Sun": 0.9856,
    "Moon": 13.1764,
    "Mercury": 1.383,
    "Venus": 1.200,
    "Mars": 0.524
}

# أرباب البيوت (Domicile Rulers)
SIGN_RULERS = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
    4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
    8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

# الشرف (Exaltations) مع درجة الشرف الدقيقة
EXALTATIONS = {
    "Sun": (0, 19.0),     # الحمل 19
    "Moon": (1, 3.0),     # الثور 3
    "Mercury": (5, 15.0), # العذراء 15
    "Venus": (11, 27.0),  # الحوت 27
    "Mars": (9, 28.0)     # الجدي 28
}

# الوبال (Detriments)
DETRIMENTS = {
    "Sun": [10],
    "Moon": [9],
    "Mercury": [8, 11],
    "Venus": [0, 7],
    "Mars": [1, 6]
}

# الهبوط (Falls)
FALLS = {
    "Sun": 6,      # الميزان
    "Moon": 7,     # العقرب
    "Mercury": 11, # الحوت
    "Venus": 5,    # العذراء
    "Mars": 3      # السرطان
}

# المثلثات الفلكية (Triplicity Rulers: النهاري، الليلي، الشريك)
# العناصر: 0=ناري (0,4,8)، 1=ترابي (1,5,9)، 2=هوائي (2,6,10)، 3=مائي (3,7,11)
TRIPLICITY_RULERS = {
    0: ("Sun", "Jupiter", "Saturn"),     # ناري
    1: ("Venus", "Moon", "Mars"),        # ترابي
    2: ("Saturn", "Mercury", "Jupiter"), # هوائي
    3: ("Venus", "Mars", "Moon")         # مائي
}

# الحدود المصرية (Egyptian Terms / Bounds): قائمة (الحد الأعلى للدرجة، الكوكب)
EGYPTIAN_TERMS = {
    0: [(6, "Jupiter"), (12, "Venus"), (20, "Mercury"), (25, "Mars"), (30, "Saturn")],   # الحمل
    1: [(8, "Venus"), (14, "Mercury"), (22, "Jupiter"), (27, "Saturn"), (30, "Mars")],   # الثور
    2: [(6, "Mercury"), (12, "Jupiter"), (17, "Venus"), (24, "Mars"), (30, "Saturn")],   # الجوزاء
    3: [(7, "Mars"), (13, "Venus"), (19, "Mercury"), (26, "Jupiter"), (30, "Saturn")],   # السرطان
    4: [(6, "Jupiter"), (11, "Venus"), (18, "Saturn"), (24, "Mercury"), (30, "Mars")],   # الأسد
    5: [(7, "Mercury"), (17, "Venus"), (21, "Jupiter"), (28, "Mars"), (30, "Saturn")],   # العذراء
    6: [(6, "Saturn"), (14, "Mercury"), (21, "Jupiter"), (28, "Venus"), (30, "Mars")],   # الميزان
    7: [(7, "Mars"), (11, "Venus"), (19, "Mercury"), (24, "Jupiter"), (30, "Saturn")],   # العقرب
    8: [(12, "Jupiter"), (17, "Venus"), (21, "Mercury"), (26, "Saturn"), (30, "Mars")],  # القوس
    9: [(7, "Mercury"), (14, "Jupiter"), (22, "Venus"), (26, "Saturn"), (30, "Mars")],   # الجدي
    10: [(7, "Mercury"), (13, "Venus"), (20, "Jupiter"), (25, "Mars"), (30, "Saturn")],  # الدلو
    11: [(12, "Venus"), (16, "Jupiter"), (19, "Mercury"), (28, "Mars"), (30, "Saturn")]  # الحوت
}

# الوجوه / العشريات الكلدانية (Chaldea Faces / Decans)
CHALDEAN_ORDER = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]

# الكويكبات الرئيسية وكيرون
ASTEROIDS_IDS = {
    "Chiron": swe.CHIRON,
    "Ceres": swe.CERES,
    "Pallas": swe.PALLAS,
    "Juno": swe.JUNO,
    "Vesta": swe.VESTA
}

ASTEROIDS_AR = {
    "Chiron": "كيرون (المعالج)",
    "Ceres": "سيريس (الأمومة والغذاء)",
    "Pallas": "بالاس (الحكمة)",
    "Juno": "جونو (عقد الزواج والشراكة)",
    "Vesta": "فيستا (الالتزام والبيت)"
}

# أهم النجوم الثابتة وتأثيرها التنجيمي: (الاسم في إيفيميريس، الاسم العربي، الطبيعة/الوزن)
FIXED_STARS_CATALOG = [
    ("Regulus", "قلب الأسد (Regulus)", +5.0, "نجم ملكي: مجد وقيادة ورفعة"),
    ("Spica", "السماك الأعزل (Spica)", +5.5, "أعظم نجوم الحظ والمواهب والحماية"),
    ("Aldebaran", "الدبران (Aldebaran)", +3.5, "نجم ملكي: نجاح وشجاعة بشرط النزاهة"),
    ("Antares", "قلب العقرب (Antares)", +2.5, "نجم ملكي: قوة عاطفية وحسم"),
    ("Fomalhaut", "فم الحوت (Fomalhaut)", +3.5, "نجم ملكي: مثالية وتألق روحي"),
    ("Sirius", "الشعرى اليمانية (Sirius)", +4.5, "تألق وشهرة ونجاح استثنائي"),
    ("Vega", "النسر الواقع (Vega)", +3.0, "جاذبية فنية وكاريزما وسحر"),
    ("Arcturus", "السماك الرامح (Arcturus)", +3.5, "ريادة وعدالة وثروة"),
    ("Algol", "رأس الغول (Algol)", -5.5, "نجم عنيف: حدة وتوتر شديد"),
    ("Alcyone", "الثريا (Alcyone)", -2.5, "حساسية عاطفية وتقلبات")
]

# =============================================================================
# 4. دوال الحسابات الفلكية والهندسية الدقيقة
# =============================================================================
def angular_diff(lon1: float, lon2: float) -> float:
    """حساب أقصر مسافة زاوية على الدائرة البروجية (0 إلى 180 درجة)."""
    diff = abs(lon1 - lon2) % 360.0
    return min(diff, 360.0 - diff)

def get_aspect_details(lon1: float, lon2: float) -> Optional[Tuple[str, float, float]]:
    """
    تحديد نوع الاتصال الفلكي والاورب المتبقي ومعامل الدقة (0.6 إلى 1.0).
    """
    dist = angular_diff(lon1, lon2)
    aspects_rules = [
        ("اقتران (0°)", 0.0, 8.0),
        ("مقابلة (180°)", 180.0, 8.0),
        ("تثليث (120°)", 120.0, 7.0),
        ("تربيع (90°)", 90.0, 7.0),
        ("تسديس (60°)", 60.0, 5.0),
    ]
    for asp_name, target_angle, max_orb in aspects_rules:
        orb = abs(dist - target_angle)
        if orb <= max_orb:
            precision_factor = 1.0 - (orb / max_orb) * 0.4
            return asp_name, orb, precision_factor
    return None

def get_term_ruler(sign_idx: int, deg_in_sign: float) -> str:
    """استخراج رب الحد المصري للدرجة داخل البرج."""
    for limit, ruler in EGYPTIAN_TERMS[sign_idx]:
        if deg_in_sign < limit:
            return ruler
    return EGYPTIAN_TERMS[sign_idx][-1][1]

def get_face_ruler(sign_idx: int, deg_in_sign: float) -> str:
    """استخراج رب الوجه (العشرية) وفق الترتيب الكلداني."""
    decan_idx = min(2, int(deg_in_sign // 10))
    total_decan = sign_idx * 3 + decan_idx
    return CHALDEAN_ORDER[total_decan % 7]

def compute_fixed_stars(jd: float) -> List[Dict[str, Any]]:
    """حساب المواقع الدقيقة للنجوم الثابتة في لحظة الميلاد مع تصحيح مبادرة الاعتدالين."""
    stars_positions = []
    for star_key, star_ar, weight, desc in FIXED_STARS_CATALOG:
        try:
            res, _ = swe.fixstar2_ut(star_key, jd)
            stars_positions.append({
                "key": star_key,
                "name_ar": star_ar,
                "lon": res[0],
                "weight": weight,
                "desc": desc
            })
        except Exception:
            continue
    return stars_positions

# =============================================================================
# 5. محرك تقييم قوى الكواكب الشخصية (مقياس 100 نقطة شامل الكرامات والاتصالات)
# =============================================================================
def evaluate_planet_100_scale(
    planet_name: str,
    all_planets: Dict[str, Dict[str, Any]],
    asteroids: Dict[str, Dict[str, Any]],
    fixed_stars: List[Dict[str, Any]],
    is_day_chart: bool,
    has_birth_time: bool
) -> Tuple[float, List[str], Dict[str, float]]:
    """
    حساب قوة الكوكب الشخصي من أصل 100 نقطة بدمج:
    - الكرامات الذاتية الخمس (البيت، الشرف، المثلثة، الحد، الوجه) والانتكاسات (الوبال، الهبوط، الغربة)
    - التبادل بالربوبية (Mutual Reception)
    - الكرامات العرضية: البيوت، السرعة، التراجع، الموقف من الشمس (Cazimi / Combust / Under Beams)، الحيّز
    - اتصالات الكواكب العشرة، الكويكبات الخمسة، والنجوم الثابتة
    """
    p_data = all_planets[planet_name]
    p_lon = p_data["lon"]
    p_speed = p_data["speed"]
    sign_idx = p_data["sign_idx"]
    deg_in_sign = p_data["deg_in_sign"]
    house_num = p_data["whole_sign_house"]

    # نقطة الأساس المحايدة = 40.0 ليتيح النطاق الوصول إلى 100 أو الهبوط تحت 50 والصفر
    score = 40.0
    breakdown = {
        "essential": 0.0,
        "accidental": 0.0,
        "planets_aspects": 0.0,
        "asteroids_stars": 0.0
    }
    reasons: List[str] = ["نقطة الأساس: 40.0"]
    has_any_essential_dignity = False

    # -------------------------------------------------------------------------
    # أ) الكرامات الذاتية الخمس (Essential Dignities)
    # -------------------------------------------------------------------------
    # 1. البيت (Domicile)
    if SIGN_RULERS.get(sign_idx) == planet_name:
        score += 12.0
        breakdown["essential"] += 12.0
        has_any_essential_dignity = True
        reasons.append("في بيته (Domicile) [+12.0]")

    # 2. الشرف (Exaltation)
    exalt_info = EXALTATIONS.get(planet_name)
    if exalt_info and exalt_info[0] == sign_idx:
        score += 15.0
        breakdown["essential"] += 15.0
        has_any_essential_dignity = True
        reasons.append("في شرفه (Exaltation) [+15.0]")
        if abs(deg_in_sign - exalt_info[1]) <= 1.5:
            score += 3.0
            breakdown["essential"] += 3.0
            reasons.append("في درجة الشرف الدقيقة [+3.0]")

    # 3. المثلثة (Triplicity)
    element_idx = sign_idx % 4
    day_ruler, night_ruler, part_ruler = TRIPLICITY_RULERS[element_idx]
    primary_trip = day_ruler if is_day_chart else night_ruler
    if planet_name == primary_trip:
        score += 7.0
        breakdown["essential"] += 7.0
        has_any_essential_dignity = True
        reasons.append("رب المثلثة الأساسي [+7.0]")
    elif planet_name == part_ruler:
        score += 4.0
        breakdown["essential"] += 4.0
        has_any_essential_dignity = True
        reasons.append("شريك المثلثة [+4.0]")

    # 4. الحد المصري (Egyptian Term / Bound)
    if get_term_ruler(sign_idx, deg_in_sign) == planet_name:
        score += 5.0
        breakdown["essential"] += 5.0
        has_any_essential_dignity = True
        reasons.append("في حده المصري (Term) [+5.0]")

    # 5. الوجه / العشرية (Face / Decan)
    if get_face_ruler(sign_idx, deg_in_sign) == planet_name:
        score += 3.0
        breakdown["essential"] += 3.0
        has_any_essential_dignity = True
        reasons.append("في وجهه (Face/Decan) [+3.0]")

    # -------------------------------------------------------------------------
    # ب) الانتكاسات الذاتية (Debilities) والغربة (Peregrine)
    # -------------------------------------------------------------------------
    is_detriment = sign_idx in DETRIMENTS.get(planet_name, [])
    is_fall = (FALLS.get(planet_name) == sign_idx)

    if is_detriment and is_fall:
        score -= 18.0
        breakdown["essential"] -= 18.0
        reasons.append("في وباله وهبوطه معاً [-18.0]")
    else:
        if is_detriment:
            score -= 12.0
            breakdown["essential"] -= 12.0
            reasons.append("في وباله (Detriment) [-12.0]")
        if is_fall:
            score -= 15.0
            breakdown["essential"] -= 15.0
            reasons.append("في هبوطه (Fall) [-15.0]")

    if not has_any_essential_dignity and not is_detriment and not is_fall:
        score -= 5.0
        breakdown["essential"] -= 5.0
        reasons.append("غريب بلا حظ ذاتي (Peregrine) [-5.0]")

    # -------------------------------------------------------------------------
    # ج) التبادل بالربوبية (Mutual Reception) مع الكواكب الأخرى
    # -------------------------------------------------------------------------
    host_ruler = SIGN_RULERS.get(sign_idx)
    if host_ruler and host_ruler != planet_name and host_ruler in all_planets:
        host_sign = all_planets[host_ruler]["sign_idx"]
        if SIGN_RULERS.get(host_sign) == planet_name:
            score += 10.0
            breakdown["essential"] += 10.0
            reasons.append(f"تبادل كامل بالبيت مع {ALL_PLANETS_AR[host_ruler]} [+10.0]")
        elif EXALTATIONS.get(planet_name) and EXALTATIONS[planet_name][0] == host_sign:
            score += 7.0
            breakdown["essential"] += 7.0
            reasons.append(f"تبادل مختلط (بيت/شرف) مع {ALL_PLANETS_AR[host_ruler]} [+7.0]")

    # -------------------------------------------------------------------------
    # د) الكرامات العرضية: البيوت، السرعة، التراجع، الموقف من الشمس، الحيّز
    # -------------------------------------------------------------------------
    # 1. قوة البيت الفلكي (عند توفر ساعة الميلاد)
    if has_birth_time:
        if house_num in [1, 10]:
            score += 10.0
            breakdown["accidental"] += 10.0
            reasons.append(f"في وتد رئيسي (البيت {house_num}) [+10.0]")
        elif house_num in [4, 7]:
            score += 8.0
            breakdown["accidental"] += 8.0
            reasons.append(f"في وتد (البيت {house_num}) [+8.0]")
        elif house_num in [5, 11]:
            score += 6.0
            breakdown["accidental"] += 6.0
            reasons.append(f"في بيت سعيد (البيت {house_num}) [+6.0]")
        elif house_num in [2, 9]:
            score += 4.0
            breakdown["accidental"] += 4.0
            reasons.append(f"في بيت داعم (البيت {house_num}) [+4.0]")
        elif house_num == 3:
            score += 1.0
            breakdown["accidental"] += 1.0
            reasons.append("في البيت 3 (فرح القمر) [+1.0]")
        elif house_num in [6, 8, 12]:
            score -= 7.0
            breakdown["accidental"] -= 7.0
            reasons.append(f"في بيت ساقط نحيس (البيت {house_num}) [-7.0]")

    # 2. الحركة اليومية (السرعة والتراجع والتوقف)
    avg_spd = AVERAGE_DAILY_SPEEDS[planet_name]
    if planet_name not in ["Sun", "Moon"]:
        if p_speed < 0:
            score -= 8.0
            breakdown["accidental"] -= 8.0
            reasons.append(f"متراجع (Retrograde: {p_speed:.2f}°/يوم) [-8.0]")
        elif abs(p_speed) < 0.08:
            score -= 4.0
            breakdown["accidental"] -= 4.0
            reasons.append("متوقف (Stationary) [-4.0]")
        else:
            if p_speed > avg_spd * 1.15:
                score += 4.0
                breakdown["accidental"] += 4.0
                reasons.append("سريع الحركة فوق المعدل [+4.0]")
            elif p_speed < avg_spd * 0.65:
                score -= 3.0
                breakdown["accidental"] -= 3.0
                reasons.append("بطيء الحركة [-3.0]")
            else:
                score += 2.0
                breakdown["accidental"] += 2.0
                reasons.append("مستقيم الحركة المعتدلة [+2.0]")
    else:
        if p_speed > avg_spd * 1.05:
            score += 3.0
            breakdown["accidental"] += 3.0
            reasons.append("سريع السير [+3.0]")
        elif p_speed < avg_spd * 0.92:
            score -= 2.0
            breakdown["accidental"] -= 2.0
            reasons.append("بطيء السير [-2.0]")

    # 3. الموقف من الشمس (Cazimi / Combust / Under the Beams)
    if planet_name != "Sun":
        sun_dist = angular_diff(p_lon, all_planets["Sun"]["lon"])
        if sun_dist <= 0.2833:  # 17 دقيقة قوسية (صميم الشمس)
            score += 12.0
            breakdown["accidental"] += 12.0
            reasons.append("في صميم الشمس (Cazimi) [+12.0]")
        elif sun_dist <= 8.5:
            # تخفيف الاحتراق إذا كان الكوكب في بيته أو شرفه
            combust_pen = -5.0 if (SIGN_RULERS.get(sign_idx) == planet_name or (exalt_info and exalt_info[0] == sign_idx)) else -10.0
            score += combust_pen
            breakdown["accidental"] += combust_pen
            reasons.append(f"محترق بالشمس ({sun_dist:.1f}°) [{combust_pen}]")
        elif sun_dist <= 17.0:
            score -= 5.0
            breakdown["accidental"] -= 5.0
            reasons.append(f"تحت شعاع الشمس ({sun_dist:.1f}°) [-5.0]")
        else:
            score += 2.0
            breakdown["accidental"] += 2.0
            reasons.append("بريء من الاحتراق (حُر من الشعاع) [+2.0]")

    # 4. الحيّز الفلكي (Sect / Diurnal-Nocturnal Alignment)
    diurnal_planets = ["Sun", "Jupiter", "Saturn"]
    nocturnal_planets = ["Moon", "Venus", "Mars"]
    if (is_day_chart and planet_name in diurnal_planets) or (not is_day_chart and planet_name in nocturnal_planets):
        score += 3.0
        breakdown["accidental"] += 3.0
        reasons.append("موافق للحيّز (نهاري/ليلي) [+3.0]")

    # -------------------------------------------------------------------------
    # هـ) اتصالات الكواكب العشرة (Planets Aspects)
    # -------------------------------------------------------------------------
    benefics = ["Jupiter", "Venus"]
    malefics = ["Saturn", "Mars"]
    outers_hard = ["Uranus", "Neptune", "Pluto"]

    for other_p, other_info in all_planets.items():
        if other_p == planet_name:
            continue
        asp_res = get_aspect_details(p_lon, other_info["lon"])
        if not asp_res:
            continue

        asp_name, orb, prec = asp_res
        other_ar = ALL_PLANETS_AR[other_p]
        delta = 0.0

        if asp_name in ["تثليث (120°)", "تسديس (60°)"]:
            base_w = 5.5 if other_p in benefics else (4.0 if other_p in ["Sun", "Moon", "Mercury"] else 3.0)
            delta = round(base_w * prec, 1)
        elif asp_name == "اقتران (0°)":
            if other_p in benefics:
                delta = round(6.5 * prec, 1)
            elif other_p in malefics:
                delta = round(-6.5 * prec, 1)
            elif other_p in outers_hard:
                delta = round(-4.5 * prec, 1)
            else:
                delta = round(4.0 * prec, 1)
        elif asp_name in ["تربيع (90°)", "مقابلة (180°)"]:
            if other_p in malefics:
                delta = round(-6.5 * prec, 1)
            elif other_p in outers_hard:
                delta = round(-5.0 * prec, 1)
            elif other_p in benefics:
                delta = round(-2.0 * prec, 1)  # تربيع السعدين أخف وطأة
            else:
                delta = round(-3.5 * prec, 1)

        if delta != 0.0:
            score += delta
            breakdown["planets_aspects"] += delta
            sign_str = "+" if delta > 0 else ""
            reasons.append(f"{asp_name} مع {other_ar} (أورب {orb:.1f}°) [{sign_str}{delta}]")

    # -------------------------------------------------------------------------
    # و) اتصالات الكويكبات الخمسة (Asteroids & Chiron)
    # -------------------------------------------------------------------------
    for ast_name, ast_info in asteroids.items():
        dist = angular_diff(p_lon, ast_info["lon"])
        ast_ar = ASTEROIDS_AR[ast_name]
        delta = 0.0
        if dist <= 3.0:
            if ast_name in ["Juno", "Ceres", "Vesta", "Pallas"]:
                delta = 2.5
                reasons.append(f"اقتران مع كويكب {ast_ar} [+2.5]")
            elif ast_name == "Chiron":
                delta = -2.5
                reasons.append(f"اقتران مع {ast_ar} [-2.5]")
        elif abs(dist - 120.0) <= 2.5 or abs(dist - 60.0) <= 2.5:
            delta = 1.5
            reasons.append(f"اتصال سعيد مع {ast_ar} [+1.5]")
        elif abs(dist - 90.0) <= 2.5 or abs(dist - 180.0) <= 2.5:
            delta = -1.5
            reasons.append(f"اتصال ضاغط مع {ast_ar} [-1.5]")

        if delta != 0.0:
            score += delta
            breakdown["asteroids_stars"] += delta

    # -------------------------------------------------------------------------
    # ز) اقتران ومقابلة النجوم الثابتة الكبرى (Fixed Stars - Orb 1.5°)
    # -------------------------------------------------------------------------
    for star in fixed_stars:
        dist = angular_diff(p_lon, star["lon"])
        if dist <= 1.5:
            w = star["weight"]
            score += w
            breakdown["asteroids_stars"] += w
            sign_str = "+" if w > 0 else ""
            reasons.append(f"اقتران بالنجم الثابت {star['name_ar']} ({star['desc']}) [{sign_str}{w}]")
        elif abs(dist - 180.0) <= 1.2 and star["weight"] < 0:
            w = round(star["weight"] * 0.6, 1)
            score += w
            breakdown["asteroids_stars"] += w
            reasons.append(f"مقابلة النجم الثابت {star['name_ar']} [{w}]")

    # السقف الأعلى 100 نقطة، ويسمح بالقيم تحت 50 أو الصفر أو السالب لإظهار الضعف بدقة
    final_score = round(min(100.0, score), 1)
    return final_score, reasons, breakdown

def get_strength_classification(score: float) -> Tuple[str, str, str]:
    """
    تصنيف قوة الكوكب حسب القاعدة المعتمدة:
    - أكثر من 60 (> 60): قوي
    - من 50 إلى 60 (50 <= score <= 60): متوسط القوى
    - أقل من 50 أو صفر أو سالب (< 50): ضعيف
    """
    if score > 60.0:
        return "قوي", "🟢", "strong"
    elif 50.0 <= score <= 60.0:
        return "متوسط القوى", "🟡", "moderate"
    else:
        return "ضعيف", "🔴", "weak"

# =============================================================================
# 6. دالة تقديم الحلول والعلاجات الفلكية المتقدمة وفق أحدث مراجع التنجيم الغربي
# =============================================================================
def get_advanced_recommendations(
    gender: str,
    venus_sc: float,
    moon_sc: float,
    sun_sc: float,
    mars_sc: float,
    fem_power: float,
    masc_power: float
) -> List[str]:
    recommendations = []
    
    is_venus_strong = venus_sc > 60.0
    is_moon_strong = moon_sc > 60.0
    is_sun_strong = sun_sc > 60.0
    is_mars_strong = mars_sc > 60.0
    
    if gender == "أنثى":
        if is_venus_strong and is_moon_strong and (fem_power > masc_power):
            recommendations.append("✨ **حالة متوازنة وممتازة:** لا تحتاجين إلى نصائح إضافية، فطاقة الأنوثة والقمر والزهرة تجاوزت 60 نقطة وهي في أعلى مستويات التناغم الداخلي والخارجي وفقاً لدلائل التنجيم الحديث.")
        else:
            if is_venus_strong and not is_moon_strong:
                recommendations.append("🏡 **دعم الجانب المنزلي والعاطفي (تقوية كوكب القمر فلكياً):**")
                recommendations.append("جلب مربية أو مساعدة كفوءة لتنظيم التدبير المنزلي ورعاية الشؤون اليومية.")
                recommendations.append("قراءة كتب تعليم الطبخ، فن التدبير المنزلي، وكيفية الاعتناء بالأطفال وتربيتهم التربية الواعية.")
                recommendations.append("🌙 **فلكياً - تقوية طاقة القمر (وفق مراجع التنجيم الغربي الحديث وعلم الأعشاب الطبية):**")
                recommendations.append("**دلائل القمر:** الارتباط بالطبيعة الدورية، الهدوء الداخلي، العناية بالبيئة المنزلية، والاتصال العاطفي العميق بالماء والحدائق.")
                recommendations.append("**الأعشاب:** البابونج الألماني، زهرة الآلام (Passionflower)، والمليسا (تُشرب على شكل منقوع فاتر مساءً للاسترخاء العاطفي).")
                recommendations.append("**الأطعمة:** الخضروات الورقية ذات الأوراق العريضة، الأغذية الغنية بالسوائل الطبيعية، منتجات الألبان الطازجة، والقرع.")
                recommendations.append("**المشروبات:** الماء النقي المفوّر، الحليب النباتي أو الحيواني الدافئ مع قليل من العسل الطبيعي.")
            
            if not is_venus_strong and is_moon_strong:
                recommendations.append("💖 **دعم جانب الثقافة الزوجية والعلاقة (تقوية كوكب الزهرة فلكياً):**")
                recommendations.append("زيادة قراءة كتب الثقافة الزوجية، فن الحوار مع الشريك، وأسس بناء العلاقات العاطفية الناجحة.")
                recommendations.append("🌹 **فلكياً - تقوية طاقة الزهرة (وفق مراجع التنجيم الغربي الحديث):**")
                recommendations.append("**دلائل الزهرة:** الجمال الحسي، الانسجام والتوافق، العناية بالمظهر الراقي، وتنسيق البيئة المحيطة بالألوان الهادئة والعطور الزكية.")
                recommendations.append("**الأعشاب:** بتلات الورد المحمدي، الفانيليا الطبيعية، واللافندر (تُستعمل كشراب لطيف أو عطور منزلية مهدئة).")
                recommendations.append("**الأطعمة:** الفواكه الطازجة ذات الطابع الحلو والمغذي (التوت البري، الفراولة، التين، والرمان)، الشوكولاتة الداكنة النقية.")
                recommendations.append("**المشروبات:** شاي بتلات الورد الفاتر، العصائر الطبيعية المنسقة بعناية.")
            
            if (not is_venus_strong and not is_moon_strong) or (fem_power <= masc_power):
                recommendations.append("🛠️ **برنامج متكامل لتعزيز مهارات الزواج والتدبير (تقوية الزهرة والقمر معاً):**")
                recommendations.append("قراءة كتب الثقافة الزوجية وبناء الألفة والتفاهم المستدام.")
                recommendations.append("جلب مربية أو مساعدة للتدبير المنزلي وتنظيم شؤون الأسرة.")
                recommendations.append("قراءة كتب تعليم الطبخ، التدبير المنزلي، وأصول تربية الأطفال الحديثة.")
                recommendations.append("🌸 **فلكياً - تقوية طاقة الزهرة والقمر:**")
                recommendations.append("**دلائل الزهرة:** الجمال الحسي، الانسجام والتوافق، العناية بالمظهر الراقي، وتنسيق البيئة المحيطة بالألوان الهادئة والعطور الزكية.")
                recommendations.append("**دلائل القمر:** الارتباط بالطبيعة الدورية، الهدوء الداخلي، العناية بالبيئة المنزلية، والاتصال العاطفي العميق بالماء والحدائق.")
                recommendations.append("**الأعشاب:** دمج البابونج (للقمر) مع بتلات الورد (للزهرة) في منقوع مسائي مهدئ.")
                recommendations.append("**الأطعمة والمشروبات:** التركيز على الأغذية الطازجة المتوازنة، شرب السوائل بانتظام، والاهتمام بالجانب الجمالي للوجبات الغذائية.")

    else:  # ذكر
        if (masc_power > fem_power) and is_sun_strong and is_mars_strong:
            recommendations.append("👑 **حالة ذكورية قيادية متوازنة:** لا تحتاج إلى نصائح إضافية، فطاقة الشمس والمريخ تتجاوز 60 نقطة وتدعمك بكفاءة عالية للقيادة وتحمل المسؤولية والإنجاب.")
        else:
            if is_sun_strong and not is_mars_strong:
                recommendations.append("🛠️ **دعم الجانب البدني والمهاري المنزلي (تقوية كوكب المريخ فلكياً):**")
                recommendations.append("التعاقد مع شركة صيانة منزلية دورية أو التسجيل في دورات متخصصة في أعمال الصيانة اليدوية والمنزلية.")
                recommendations.append("الاهتمام بالتمارين الرياضية المنتظمة، اللياقة البدنية، والصحة الإنجابية والجسدية.")
                recommendations.append("🔥 **فلكياً - تقوية طاقة المريخ (وفق مراجع التنجيم الغربي الحديث):**")
                recommendations.append("**دلائل المريخ:** الحركة الجسدية الواعية، النشاط الرياضي، الحيوية الحركية، والشجاعة في مواجهة التحديات العملية.")
                recommendations.append("**الأعشاب:** جذور الزنجبيل الطازج، القرفة، والزعتر البري (تُشرب كمغلي دافئ لتحفيز الدورة الدموية وطاقة الحركة).")
                recommendations.append("**الأطعمة:** اللحوم الحمراء الصحية، البروتينات عالية الجودة، التوابل الدافئة المعتدلة (الفلفل الأسود، الثوم)، والمكسرات الغنية بالطاقة.")
                recommendations.append("**المشروبات:** شاي الزنجبيل بالقرفة، المشروبات الدافئة المنشطة للطاقة الجسدية.")
            
            if not is_sun_strong and is_mars_strong:
                recommendations.append("👔 **دعم الجانب القيادي والإداري الأسري (تقوية كوكب الشمس فلكياً):**")
                recommendations.append("حضور دورات تدريبية متخصصة في تقوية الشخصية، الإدارة الاستراتيجية، والقيادة الأسرية الفعالة.")
                recommendations.append("☀️ **فلكياً - تقوية طاقة الشمس (وفق مراجع التنجيم الغربي الحديث):**")
                recommendations.append("**دلائل الشمس:** الحيوية المركزية، الوضوح الإداري، الثقة العالية بالنفس، والتعرض المعتدل لأشعة الشمس الصباحية لبناء الطاقة الحيوية.")
                recommendations.append("**الأعشاب:** إكليل الجبل (الروزماري)، عشبة الليمون (Lemongrass)، والبابونج الإيجابي.")
                recommendations.append("**الأطعمة:** الحمضيات الطازجة الغنية بفيتامين سي (البرتقال، الليمون، الجريب فروت)، الحبوب الكاملة، والعسل الطبيعي النقي.")
                recommendations.append("**المشروبات:** ماء دافئ مع قطرات الليمون الطازج صباحاً، شاي إكليل الجبل المنعش.")
            
            if (not is_sun_strong and not is_mars_strong) or (masc_power <= fem_power):
                recommendations.append("🚀 **برنامج مكثف لتطوير المهارات الشخصية والقيادية والمنزلية (تقوية الشمس والمريخ معاً):**")
                recommendations.append("الانتظام في التمارين الرياضية وبناء اللياقة البدنية بانتظام.")
                recommendations.append("حضور دورات متخصصة في تطوير الذات، تقوية الشخصية، والثقة بالنفس.")
                recommendations.append("حضور دورات تدريبية في الصيانة المنزلية وإدارة شؤون البيت الأساسية.")
                recommendations.append("⚡ **فلكياً - تقوية طاقة المريخ والشمس:**")
                recommendations.append("**دلائل المريخ:** الحركة الجسدية الواعية، النشاط الرياضي، الحيوية الحركية، والشجاعة في مواجهة التحديات العملية.")
                recommendations.append("**دلائل الشمس:** الحيوية المركزية، الوضوح الإداري، الثقة العالية بالنفس، والتعرض المعتدل لأشعة الشمس الصباحية لبناء الطاقة الحيوية.")
                recommendations.append("**الأعشاب والمشروبات:** شاي الزنجبيل والقرفة صباحاً (للمريخ) مع شاي إكليل الجبل والليمون عصراً (للشمس).")
                recommendations.append("**الأطعمة:** الأغذية الغنية بالبروتين، الخضروات الجذرية الطازجة، الحمضيات، والعسل الطبيعي.")

    return recommendations

# =============================================================================
# 7. مولد تقرير HTML الاحترافي للطباعة (Print-Ready Executive Report)
# =============================================================================
def generate_html_report(data: Dict[str, Any]) -> str:
    planets_rows = ""
    for p_name in PERSONAL_PLANETS:
        p_info = data["all_planets"][p_name]
        sc = data["scores"][p_name]
        reasons_html = "".join([f"<span class='tag'>{r}</span>" for r in data["reasons"][p_name]])
        lbl, icon, status_cls = get_strength_classification(sc)
        badge_style = (
            "background:#dcfce7; color:#166534; border:1px solid #86efac;" if status_cls == "strong"
            else ("background:#fef9c3; color:#854d0e; border:1px solid #fde047;" if status_cls == "moderate"
                  else "background:#fee2e2; color:#991b1b; border:1px solid #fca5a5;")
        )
        retro_badge = " <span style='color:#dc2626; font-weight:bold;'>(R متراجع)</span>" if p_info["speed"] < 0 else ""
        planets_rows += f"""
        <tr>
            <td style="font-weight:800; font-size:15px;">{ALL_PLANETS_AR[p_name]}{retro_badge}</td>
            <td>{p_info['sign_name']} ({p_info['deg_in_sign']:.2f}°)</td>
            <td style="text-align:center;">البيت {p_info['whole_sign_house']}</td>
            <td style="text-align:center; font-weight:900; font-size:16px;">{sc:.1f} / 100</td>
            <td style="text-align:center;">
                <span style="padding:5px 12px; border-radius:20px; font-weight:700; font-size:12px; display:inline-block; {badge_style}">
                    {icon} {lbl}
                </span>
            </td>
            <td style="font-size:11.5px; color:#334155; line-height:1.7;">{reasons_html}</td>
        </tr>
        """

    outer_rows = ""
    for p_name in ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
        p_info = data["all_planets"][p_name]
        retro_txt = "متراجع (R)" if p_info["speed"] < 0 else "مستقيم (D)"
        outer_rows += f"""
        <tr>
            <td style="font-weight:700;">{ALL_PLANETS_AR[p_name]}</td>
            <td>{p_info['sign_name']} ({p_info['deg_in_sign']:.2f}°)</td>
            <td style="text-align:center;">البيت {p_info['whole_sign_house']}</td>
            <td style="text-align:center;">{retro_txt}</td>
        </tr>
        """

    bullets_html = "".join([f"<li>{b}</li>" for b in data["diag_bullets"]])
    
    recs_html = ""
    for r in data["recommendations"]:
        clean_r = r.replace("**", "")
        if r.startswith(("✨", "🏡", "💖", "🛠️", "👑", "👔", "🔥", "☀️", "🚀", "🌙", "🌹", "🌸", "⚡")):
            recs_html += f"<h4 style='color:#1e3a8a; margin:14px 0 6px 0;'>{clean_r}</h4>"
        else:
            recs_html += f"<p style='margin:4px 0 4px 12px;'>• {clean_r}</p>"

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تقرير التقييم الفلكي الشامل (مقياس 100 نقطة) - {data['name']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@700&family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Cairo', sans-serif;
            direction: rtl;
            text-align: right;
            background: #f1f5f9;
            color: #0f172a;
            padding: 25px;
            margin: 0;
            font-size: 13.5px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 35px;
            border-radius: 14px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 6px 25px rgba(0,0,0,0.07);
        }}
        .header {{
            text-align: center;
            background: linear-gradient(135deg, #090d16 0%, #172554 100%);
            color: #f8fafc;
            padding: 25px;
            border-radius: 12px;
            border: 2px solid #d4af37;
            margin-bottom: 25px;
        }}
        .header h1 {{
            font-family: 'Amiri', serif;
            color: #facc15;
            font-size: 28px;
            margin: 0 0 6px 0;
        }}
        .section-title {{
            font-size: 17px;
            font-weight: 800;
            color: #0f172a;
            border-bottom: 2px solid #d4af37;
            padding-bottom: 6px;
            margin: 24px 0 14px 0;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        .info-box {{
            background: #f8fafc;
            padding: 12px 14px;
            border-radius: 8px;
            border-right: 4px solid #d4af37;
            border: 1px solid #e2e8f0;
        }}
        .info-box span {{
            display: block;
            font-size: 11.5px;
            color: #64748b;
        }}
        .info-box strong {{
            font-size: 13.5px;
            color: #0f172a;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th {{
            background: #0f172a;
            color: #ffffff;
            padding: 10px 12px;
            text-align: right;
            font-weight: 700;
            font-size: 13px;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        .tag {{
            display: inline-block;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 5px;
            padding: 2px 6px;
            margin: 2px;
            font-size: 11px;
        }}
        .power-summary {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 18px;
        }}
        .power-card {{
            background: #fefce8;
            border: 1px solid #fde047;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }}
        .mercury-box {{
            background: #eff6ff;
            border-right: 5px solid #2563eb;
            padding: 14px 18px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        .diagnosis-box {{
            border-right: 6px solid {data['border_color']};
            background-color: {data['bg_tint']};
            border-top: 1px solid #e2e8f0;
            border-bottom: 1px solid #e2e8f0;
            border-left: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 22px;
            margin-bottom: 20px;
        }}
        .diagnosis-box h3 {{
            color: {data['title_color']};
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 18px;
        }}
        .diagnosis-box ul {{
            margin: 10px 0 0 0;
            padding-right: 22px;
            line-height: 1.8;
        }}
        .rec-box {{
            background: #f8fafc;
            border-right: 5px solid #2563eb;
            padding: 18px;
            border-radius: 8px;
            margin-top: 20px;
            border: 1px solid #e2e8f0;
            line-height: 1.85;
        }}
        .rec-box h3 {{
            color: #1e3a8a;
            margin-top: 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #cbd5e1;
            color: #64748b;
            font-size: 12px;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .container {{ box-shadow: none; border: none; padding: 10px; max-width: 100%; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>التقرير الفلكي الشامل لقوى الكواكب الشخصية وصلاحية الزواج</h1>
        <p>محرك التقييم المئوي (100 نقطة) — الكرامات الخمس، التبادل، السرعة، الشمس، الكواكب العشرة، الكويكبات والنجوم الثابتة</p>
    </div>

    <div class="section-title">البيانات الفلكية والجغرافية للحدث</div>
    <div class="info-grid">
        <div class="info-box"><span>الاسم</span><strong>{data['name']}</strong></div>
        <div class="info-box"><span>الجنس</span><strong>{data['gender']}</strong></div>
        <div class="info-box"><span>التاريخ والوقت المحلي</span><strong>{data['birth_date']} ({data['birth_time_label']})</strong></div>
        <div class="info-box"><span>التوقيت العالمي (UTC)</span><strong>{data['utc_label']}</strong></div>
        <div class="info-box"><span>الموقع الجغرافي</span><strong>{data['location']}</strong></div>
        <div class="info-box"><span>الإحداثيات والمنطقة</span><strong>{data['coords_label']} ({data['tz_str']})</strong></div>
        <div class="info-box"><span>مرجعية الطالع والبيوت</span><strong>{data['asc_label']}</strong></div>
        <div class="info-box"><span>طبيعة الخريطة (الحيّز)</span><strong>{data['sect_label']}</strong></div>
    </div>

    <div class="section-title">تقييم الكواكب الشخصية الخمسة (مقياس 100 نقطة)</div>
    <table>
        <thead>
            <tr>
                <th style="width:12%;">الكوكب</th>
                <th style="width:14%;">البرج والدرجة</th>
                <th style="width:10%; text-align:center;">البيت</th>
                <th style="width:11%; text-align:center;">النتيجة</th>
                <th style="width:13%; text-align:center;">التصنيف</th>
                <th style="width:40%;">تفصيل الكرامات، السرعة، الشمس، والاتصالات المؤثرة</th>
            </tr>
        </thead>
        <tbody>
            {planets_rows}
        </tbody>
    </table>

    <div class="section-title">مواقع الكواكب العلوية والأجيال المؤثرة في الاتصالات</div>
    <table>
        <thead>
            <tr>
                <th>الكوكب</th>
                <th>البرج والدرجة</th>
                <th style="text-align:center;">البيت (كل برج بيت)</th>
                <th style="text-align:center;">حالة السير</th>
            </tr>
        </thead>
        <tbody>
            {outer_rows}
        </tbody>
    </table>

    <div class="section-title">مقارنة الكتل الطاقية (الأنوثة مقابل الذكورة)</div>
    <div class="power-summary">
        <div class="power-card">
            <div style="font-size:13px; color:#64748b;">مجموع طاقة الأنوثة (الزهرة + القمر من 200)</div>
            <div style="font-size:24px; font-weight:900; color:#be185d;">{data['fem_power']:.1f} نقطة</div>
        </div>
        <div class="power-card">
            <div style="font-size:13px; color:#64748b;">مجموع طاقة الذكورة (الشمس + المريخ من 200)</div>
            <div style="font-size:24px; font-weight:900; color:#1d4ed8;">{data['masc_power']:.1f} نقطة</div>
        </div>
    </div>

    <div class="mercury-box">
        🧠 <strong>حالة كوكب عطارد ({data['mercury_score']:.1f} / 100 — {data['mercury_label']}):</strong> {data['mercury_text']}
    </div>

    <div class="section-title">النتيجة التشخيصية للزواج والشراكة والمسؤوليات</div>
    <div class="diagnosis-box">
        <h3>{data['diag_title']}</h3>
        <p style="font-weight:700; margin-bottom:8px;">{data['diag_summary']}</p>
        <ul>{bullets_html}</ul>
    </div>

    <div class="rec-box">
        <h3>💡 التوصيات والإرشادات العملية وعلاجات تقوية الكواكب فلكياً:</h3>
        {recs_html}
    </div>

    <div class="footer">
        <p>معيار التصنيف المئوي: أكثر من 60 = قوي | من 50 إلى 60 = متوسط القوى | أقل من 50 أو صفر أو سالب = ضعيف — استرو رادار</p>
    </div>
</div>
</body>
</html>
"""
    return html

# =============================================================================
# 8. واجهة المستخدم التفاعلية في Streamlit
# =============================================================================
st.markdown("""
<div class="main-header">
    <h1>🔭 المحرك الفلكي المتقدم لتقييم قوى الكواكب وصلاحية الزواج</h1>
    <p>نظام تقييم شمولي من 100 نقطة يدمج الكرامات الخمس، التبادل، السرعة، الشمس، الكواكب العشرة، الكويكبات والنجوم الثابتة</p>
    <p>تطوير الفلكي الدكتور استرو رادار</p>

</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("👤 البيانات الأساسية")
    name = st.text_input("الاسم أو عنوان الخريطة:", "سارة")
    gender = st.selectbox("الجنس:", ["أنثى", "ذكر"], index=0)
    birth_date = st.date_input(
        "تاريخ الميلاد / الحدث:",
        value=datetime.date(1995, 5, 15),
        min_value=datetime.date(1800, 1, 1),
        max_value=datetime.date(2100, 12, 31)
    )

    st.markdown("---")
    st.header("⏰ التوقيت المحلي")
    time_option = st.radio("دقة الساعة:", ["معرفة ساعة الميلاد", "عدم معرفة ساعة الميلاد"])
    
    birth_time_obj = datetime.time(12, 0, 0)
    if time_option == "معرفة ساعة الميلاد":
        birth_time_str = st.text_input("الساعة المحلية (HH:MM أو HH:MM:SS):", value="12:00:00")
        try:
            parts = list(map(int, birth_time_str.strip().split(":")))
            h = parts[0]
            m = parts[1] if len(parts) > 1 else 0
            s = parts[2] if len(parts) > 2 else 0
            birth_time_obj = datetime.time(h, m, s)
        except Exception:
            st.warning("⚠️ صيغة الوقت غير صحيحة، تم ضبط الوقت افتراضياً على 12:00:00.")
            birth_time_obj = datetime.time(12, 0, 0)

    st.markdown("---")
    st.header("🌍 الموقع الجغرافي")
    coord_mode = st.radio("طريقة تحديد الموقع:", ["اختيار من قائمة المدن", "إدخال الإحداثيات يدوياً (Lat/Lon)"])

    if coord_mode == "اختيار من قائمة المدن":
        selected_country_name = st.selectbox("الدولة:", country_list)
        country_code = country_map[selected_country_name]
        country_cities = cities_by_country.get(country_code, [])
        city_names = [c.name for c in country_cities]

        if city_names:
            selected_city_name = st.selectbox("المدينة:", city_names)
            selected_city = next((c for c in country_cities if c.name == selected_city_name), country_cities[0])
            lat = selected_city.latitude
            lon = selected_city.longitude
            location_label = f"{selected_city_name}, {selected_country_name}"
        else:
            lat, lon = 25.2048, 55.2708
            location_label = selected_country_name
    else:
        lat = st.number_input("خط العرض (Latitude):", min_value=-90.0, max_value=90.0, value=25.2048, format="%.4f")
        lon = st.number_input("خط الطول (Longitude):", min_value=-180.0, max_value=180.0, value=55.2708, format="%.4f")
        location_label = f"إحداثيات مخصصة ({lat:.4f}°, {lon:.4f}°)"

    tz_str = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    st.info(f"📍 الإحداثيات: `{lat:.4f}°, {lon:.4f}°`\n\n⏰ المنطقة الزمنية: `{tz_str}`")

submit = st.button("🚀 تشغيل المحرك الفلكي وتوليد التقرير المئوي", type="primary")

if submit:
    # 1. التحويل الزمني الدقيق من المحلي إلى UTC ثم Julian Day
    local_tz = pytz.timezone(tz_str)
    has_birth_time = (time_option == "معرفة ساعة الميلاد")
    naive_dt = datetime.datetime.combine(birth_date, birth_time_obj if has_birth_time else datetime.time(12, 0))
    
    try:
        localized_dt = local_tz.localize(naive_dt, is_dst=None)
    except Exception:
        try:
            localized_dt = local_tz.localize(naive_dt, is_dst=False)
        except Exception:
            localized_dt = local_tz.localize(naive_dt)

    utc_dt = localized_dt.astimezone(pytz.utc)
    decimal_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, decimal_hour)

    # 2. حساب مواقع وسرعات الكواكب العشرة
    raw_planets = {}
    for p_name, p_id in ALL_PLANETS_IDS.items():
        res, _ = swe.calc_ut(jd, p_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
        raw_planets[p_name] = {
            "lon": res[0],
            "lat": res[1],
            "speed": res[3]
        }

    # 3. حساب الطالع والبيوت بنظام كل برج بيت (Whole Sign)
    if has_birth_time:
        _, ascmc = swe.houses_ex(jd, lat, lon, b'W')
        asc_lon = ascmc[0]
        house_start_sign = int(asc_lon / 30) % 12
        asc_label = f"الطالع: {ZODIAC_NAMES_AR[house_start_sign]} ({asc_lon % 30:.2f}°)"
    else:
        house_start_sign = int(raw_planets["Sun"]["lon"] / 30) % 12
        asc_label = f"طالع شمسي تقديري: {ZODIAC_NAMES_AR[house_start_sign]}"

    all_planets_data = {}
    for p_name, p_vals in raw_planets.items():
        p_lon = p_vals["lon"]
        sign_idx = int(p_lon / 30) % 12
        whole_sign_house = ((sign_idx - house_start_sign) % 12) + 1
        all_planets_data[p_name] = {
            "lon": p_lon,
            "speed": p_vals["speed"],
            "sign_idx": sign_idx,
            "sign_name": ZODIAC_NAMES_AR[sign_idx],
            "deg_in_sign": p_lon % 30,
            "whole_sign_house": whole_sign_house
        }

    # تحديد طبيعة الخريطة (نهارية إذا كانت الشمس فوق الأفق في البيوت 7 إلى 12)
    sun_house = all_planets_data["Sun"]["whole_sign_house"]
    is_day_chart = (sun_house in [7, 8, 9, 10, 11, 12]) if has_birth_time else True
    sect_label = "خريطة نهارية (Diurnal)" if is_day_chart else "خريطة ليلية (Nocturnal)"

    # 4. حساب مواقع الكويكبات والنجوم الثابتة
    asteroids_data = {}
    for ast_name, ast_id in ASTEROIDS_IDS.items():
        try:
            res, _ = swe.calc_ut(jd, ast_id, swe.FLG_SWIEPH)
            asteroids_data[ast_name] = {"lon": res[0]}
        except Exception:
            continue

    fixed_stars_data = compute_fixed_stars(jd)

    # 5. تقييم الكواكب الشخصية الخمسة على مقياس 100 نقطة
    scores: Dict[str, float] = {}
    reasons: Dict[str, List[str]] = {}
    breakdowns: Dict[str, Dict[str, float]] = {}

    for p_name in PERSONAL_PLANETS:
        sc, r_list, b_dict = evaluate_planet_100_scale(
            planet_name=p_name,
            all_planets=all_planets_data,
            asteroids=asteroids_data,
            fixed_stars=fixed_stars_data,
            is_day_chart=is_day_chart,
            has_birth_time=has_birth_time
        )
        scores[p_name] = sc
        reasons[p_name] = r_list
        breakdowns[p_name] = b_dict

    # 6. عرض النتائج في واجهة Streamlit
    st.markdown("---")
    st.markdown(f"### 📊 التحليل الفلكي الشامل لـ ({name}) — الجنس: ({gender}) — الموقع: ({location_label})")

    col_res1, col_res2 = st.columns([1.45, 1])
    with col_res1:
        st.markdown("#### ⭐ تقييم الكواكب الشخصية (من أصل 100 نقطة):")
        for p_name in PERSONAL_PLANETS:
            sc = scores[p_name]
            lbl, icon, _ = get_strength_classification(sc)
            p_info = all_planets_data[p_name]
            retro_tag = " [متراجع R]" if p_info["speed"] < 0 else ""
            st.markdown(f"""
            <div class="planet-detail-box">
                <strong>{ALL_PLANETS_AR[p_name]}{retro_tag}</strong>: 
                <code>{sc:.1f} / 100</code> — {icon} <strong>{lbl}</strong> | 
                برج {p_info['sign_name']} ({p_info['deg_in_sign']:.2f}°) — البيت {p_info['whole_sign_house']}<br>
                <span style="font-size:12px; color:#475569;">{' • '.join(reasons[p_name])}</span>
            </div>
            """, unsafe_allow_html=True)

    with col_res2:
        st.markdown("#### ℹ️ معطيات المحرك ومعايير القياس:")
        st.info(
            f"- **التوقيت العالمي (UTC):** `{utc_dt.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"- **اليوم اليولياني (JD):** `{jd:.5f}`\n"
            f"- **مرجعية الطالع:** {asc_label} (نظام كل برج بيت)\n"
            f"- **طبيعة الخريطة:** {sect_label}\n"
            "- **نطاقات التقييم المئوي (من 100):**\n"
            "  - 🟢 **أكثر من 60 نقطة:** قوي\n"
            "  - 🟡 **من 50 إلى 60 نقطة:** متوسط القوى\n"
            "  - 🔴 **أقل من 50 (أو صفر أو سالب):** ضعيف"
        )

    sun_sc = scores["Sun"]
    moon_sc = scores["Moon"]
    mercury_sc = scores["Mercury"]
    venus_sc = scores["Venus"]
    mars_sc = scores["Mars"]

    is_sun_strong = sun_sc > 60.0
    is_moon_strong = moon_sc > 60.0
    is_mercury_strong = mercury_sc > 60.0
    is_venus_strong = venus_sc > 60.0
    is_mars_strong = mars_sc > 60.0

    fem_power = round(venus_sc + moon_sc, 1)
    masc_power = round(sun_sc + mars_sc, 1)

    st.markdown("---")
    st.markdown("### ⚖️ موازين القوى والتشخيص النهائي:")
    c_p1, c_p2 = st.columns(2)
    c_p1.metric("مجموع طاقة الأنوثة (الزهرة + القمر من 200)", f"{fem_power:.1f} نقطة")
    c_p2.metric("مجموع طاقة الذكورة (الشمس + المريخ من 200)", f"{masc_power:.1f} نقطة")

    mercury_lbl, _, _ = get_strength_classification(mercury_sc)
    if is_mercury_strong:
        mercury_text = f"عطارد قوي ({mercury_sc:.1f}/100): يدل على رجاحة العقل، سرعة الفهم، وحسن التواصل والحوار لحل الخلافات الزوجية."
        st.success(f"🟢 **{mercury_text}**")
    elif 50.0 <= mercury_sc <= 60.0:
        mercury_text = f"عطارد {mercury_lbl} ({mercury_sc:.1f}/100): التواصل الفكري متوازن ويحتاج إلى وضوح وصبر في النقاشات الدقيقة."
        st.warning(f"🟡 **{mercury_text}**")
    else:
        mercury_text = f"عطارد {mercury_lbl} ({mercury_sc:.1f}/100): يحتاج إلى جهد واعٍ في تنظيم الأفكار والحوار لتجنب سوء الفهم."
        st.error(f"🔴 **{mercury_text}**")

    # =========================================================================
    # التشخيص وشروط الأنثى والذكر وفق مقياس 100 نقطة
    # =========================================================================
    diag_title = ""
    diag_summary = ""
    diag_bullets = []
    border_color = "#d4af37"
    bg_tint = "#ffffff"
    title_color = "#0f172a"

    if gender == "أنثى":
        if fem_power <= masc_power:
            diag_title = "❌ لا تصلح للزواج لأن طاقة الذكورة مرتفعة"
            diag_summary = f"مجموع الزهرة والقمر ({fem_power:.1f}) ≤ مجموع الشمس والمريخ ({masc_power:.1f}):"
            diag_bullets = [
                "طاقة الذكورة والسيطرة والاستقلالية تطغى على الطبيعة الأنثوية.",
                "يصعب عليها التكيف مع متطلبات الزواج التقليدي أو الخضوع لسلطة الزوج، مما يولد صداماً مستمراً."
            ]
            border_color = "#ef4444"
            bg_tint = "#fef2f2"
            title_color = "#991b1b"

        elif is_venus_strong and is_moon_strong and (fem_power > masc_power):
            diag_title = "✅ تصلح للزواج، الإنجاب، رعاية الأطفال، التدبير المنزلي، والأنوثة"
            diag_summary = f"زهرة قوية ({venus_sc:.1f}) + قمر قوي ({moon_sc:.1f}) + (الزهرة + القمر > الشمس + المريخ):"
            diag_bullets = [
                "أنوثة مكتملة: الاهتمام بالجسد والزينة والعناية بالمظهر.",
                "أمومة واعية: قدرة عالية على رعاية الأطفال وتربيتهم بحنان وعاطفة صادقة.",
                "ربة منزل بارعة: إتقان التدبير المنزلي وإشاعة الدفء والاستقرار في عش الزوجية."
            ]
            border_color = "#16a34a"
            bg_tint = "#f0fdf4"
            title_color = "#166534"

        elif is_moon_strong and (venus_sc <= 60.0) and (fem_power > masc_power):
            diag_title = "🟡 تنفع للإنجاب، رعاية الأطفال، والتدبير المنزلي فقط"
            diag_summary = f"قمر قوي ({moon_sc:.1f}) + زهرة غير قوية ({venus_sc:.1f}) + (الزهرة + القمر > الشمس + المريخ):"
            diag_bullets = [
                "مؤهلة تماماً للإنجاب، رعاية الأطفال، وتدبير شؤون المنزل بمسؤولية وعملية عالية.",
                "يقل اهتمامها بالزينة الشكلية والمتع الحسية، حيث يكون تركيزها الأساسي منصباً على واجبات الأمومة والاستقرار العائلي."
            ]
            border_color = "#d97706"
            bg_tint = "#fffbeb"
            title_color = "#92400e"

        elif is_venus_strong and (moon_sc <= 60.0) and (fem_power > masc_power):
            diag_title = "💖 طاقة أنوثة (تصلح لزواج لا يحتاج أطفالاً أو تدبيراً منزلياً بل للمتعة الحسية فقط)"
            diag_summary = f"زهرة قوية ({venus_sc:.1f}) + قمر غير قوي ({moon_sc:.1f}) + (الزهرة + القمر > الشمس + المريخ):"
            diag_bullets = [
                "طاقة أنوثة طاغية وجاذبية حسية عالية مكرسة للجمال والزينة والعلاقة العاطفية المتبادلة.",
                "تصلح لزواج رفقة ومتعة حسية فقط، ولا تتوافق مع أعباء الإنجاب أو رعاية الأطفال أو التدبير المنزلي."
            ]
            border_color = "#db2777"
            bg_tint = "#fdf2f8"
            title_color = "#9d174d"

        else:
            diag_title = "🟡 صلاحية متوسطة للزواج (طاقة أنوثة معتدلة)"
            diag_summary = f"مجموع الزهرة والقمر ({fem_power:.1f}) أكبر من الشمس والمريخ ({masc_power:.1f}) بقيم متوسطة:"
            diag_bullets = [
                "تؤدي الواجبات الزوجية والمنزلية بصورة معتدلة ودون تفوق استثنائي في مجال محدد."
            ]
            border_color = "#2563eb"
            bg_tint = "#eff6ff"
            title_color = "#1e40af"

    else:  # ذكر
        if (masc_power <= fem_power) or (sun_sc <= 60.0 and mars_sc <= 60.0):
            diag_title = "❌ لا يصلح للزواج"
            diag_summary = f"مجموع (الشمس {sun_sc:.1f} + المريخ {mars_sc:.1f} = {masc_power:.1f}) ≤ (القمر + الزهرة {fem_power:.1f}) أو كلاهما ليسا في نطاق القوة (> 60):"
            diag_bullets = [
                "ضعف في مقومات القيادة وتحمل المسؤولية الزوجية والمادية.",
                "تغلب عليه الحساسية أو التردد، مما يجعله غير مؤهل للزواج وتحمل أعباء الأسرة."
            ]
            border_color = "#ef4444"
            bg_tint = "#fef2f2"
            title_color = "#991b1b"

        else:
            if is_sun_strong and is_mars_strong and (abs(sun_sc - mars_sc) <= 10.0):
                diag_title = "👑 يصلح للزواج والقيادة والعمل الشاق والإنجاب بامتياز"
                diag_summary = f"الشمس والمريخ كلاهما قويان ومتقاربان (الشمس: {sun_sc:.1f}، المريخ: {mars_sc:.1f}):"
                diag_bullets = [
                    "يجمع ببراعة بين هيبة القيادة وإدارة شؤون المنزل (الشمس) وبين القوة البدنية والعمل الشاق وإنجاب الأطفال (المريخ)."
                ]
                border_color = "#16a34a"
                bg_tint = "#f0fdf4"
                title_color = "#166534"

            elif is_sun_strong and (mars_sc <= 60.0):
                diag_title = "👔 يصلح للزواج، لكن لا يصلح للعمل الشاق أو التصليح في المنزل أو لإنجاب الأطفال"
                diag_summary = f"الشمس قوية ({sun_sc:.1f}) + المريخ غير قوي ({mars_sc:.1f}):"
                diag_bullets = [
                    "يصلح للزواج والوجاهة والقيادة واتخاذ القرارات الإدارية.",
                    "لا يصلح للأعمال البدنية الشاقة، صيانة أو تصليح مرافق المنزل، أو إنجاب الأطفال."
                ]
                border_color = "#d97706"
                bg_tint = "#fffbeb"
                title_color = "#92400e"

            elif is_mars_strong and (sun_sc <= 60.0):
                diag_title = "🛠️ يصلح لإنجاب الأطفال والعمل الشاق وتصليح المنزل، لكن غير جيد لقيادة شؤون المنزل وتحمل كامل مسؤوليته"
                diag_summary = f"المريخ قوي ({mars_sc:.1f}) + الشمس غير قوية ({sun_sc:.1f}):"
                diag_bullets = [
                    "يتمتع بطاقة جسدية عالية تجعله صالحاً لإنجاب الأطفال، العمل الشاق، والصيانة المنزلية.",
                    "غير جيد لقيادة شؤون الأسرة الإدارية أو التخطيط الاستراتيجي وتحمل كامل المسؤولية المعنوية."
                ]
                border_color = "#2563eb"
                bg_tint = "#eff6ff"
                title_color = "#1e40af"

            else:
                diag_title = "⚖️ يصلح للزواج بشكل عام (قوى ذكورية متوازنة)"
                diag_summary = f"مجموع الذكورة ({masc_power:.1f}) أكبر من الأنوثة مع قوى متباينة نسبياً (الشمس: {sun_sc:.1f}، المريخ: {mars_sc:.1f}):"
                diag_bullets = [
                    "قدرة جيدة على الارتباط وتحمل المسؤوليات مع ميل واضح لأحد جوانب القيادة أو العمل حسب قوة الكوكب الأرجح."
                ]
                border_color = "#10b981"
                bg_tint = "#f0fdf4"
                title_color = "#047857"

    bullets_ui = "".join([f"<li>{b}</li>" for b in diag_bullets])
    st.markdown(f"""
    <div class="result-card" style="border-right-color: {border_color}; background-color: {bg_tint};">
        <h3 style="color: {title_color}; margin-top: 0;">{diag_title}</h3>
        <p><strong>{diag_summary}</strong></p>
        <ul>{bullets_ui}</ul>
    </div>
    """, unsafe_allow_html=True)

    recommendations = get_advanced_recommendations(
        gender, venus_sc, moon_sc, sun_sc, mars_sc, fem_power, masc_power
    )
    
    st.markdown("""
    <div class="rec-box">
        <h3>💡 التوصيات والإرشادات العملية وعلاجات تقوية الكواكب فلكياً:</h3>
    </div>
    """, unsafe_allow_html=True)
    for rec in recommendations:
        if rec.startswith(("✨", "🏡", "💖", "🛠️", "👑", "👔", "🔥", "☀️", "🚀", "🌙", "🌹", "🌸", "⚡")):
            st.markdown(f"#### {rec}")
        else:
            st.markdown(f"- {rec}")

    # 7. تجهيز بيانات تقرير HTML القابل للطباعة
    report_payload = {
        "name": name,
        "gender": gender,
        "birth_date": birth_date.strftime("%Y-%m-%d"),
        "birth_time_label": str(birth_time_obj) if has_birth_time else "غير محددة (تقدير منتصف النهار)",
        "utc_label": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "location": location_label,
        "coords_label": f"{lat:.4f}°, {lon:.4f}°",
        "tz_str": tz_str,
        "asc_label": asc_label,
        "sect_label": sect_label,
        "all_planets": all_planets_data,
        "scores": scores,
        "reasons": reasons,
        "fem_power": fem_power,
        "masc_power": masc_power,
        "mercury_score": mercury_sc,
        "mercury_label": mercury_lbl,
        "mercury_text": mercury_text,
        "diag_title": diag_title,
        "diag_summary": diag_summary,
        "diag_bullets": diag_bullets,
        "recommendations": recommendations,
        "border_color": border_color,
        "bg_tint": bg_tint,
        "title_color": title_color
    }

    html_report = generate_html_report(report_payload)

    st.download_button(
        label=f"📥 تحميل تقرير التحليل الفلكي المئوي لـ ({name}) [HTML جاهز للطباعة]",
        data=html_report,
        file_name=f"تقرير_القوى_الفلكية_100_{name.replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True
    )
