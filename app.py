import datetime
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

import geonamescache
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder

# =============================================================================
# إعدادات Swiss Ephemeris والتنسيق البصري العربي (RTL)
# =============================================================================
swe.set_ephe_path('')  # استخدام وضع Moshier الافتراضي للتقويم الفلكي الدقيق

st.set_page_config(
    page_title="حاسبة صلاحية الزواج الفلكية المتقدمة",
    layout="wide",
    page_icon="⚖️"
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
        background: linear-gradient(135deg, #1a2a44 0%, #0d1b2a 100%);
        color: #ffffff;
        font-weight: 800;
        font-size: 17px;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #c59b27;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #c59b27 0%, #a17c18 100%);
        color: #0f172a;
        border-color: #ffd700;
        box-shadow: 0 4px 15px rgba(197, 155, 39, 0.4);
    }
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 100%);
        color: #f1f5f9;
        padding: 24px;
        border-radius: 12px;
        border: 2px solid #c59b27;
        margin-bottom: 25px;
    }
    .main-header h1 {
        font-family: 'Amiri', serif;
        color: #e6ca65;
        font-size: 28px;
        margin-bottom: 6px;
        font-weight: 700;
    }
    .result-card {
        background: #ffffff;
        border-right: 6px solid #c59b27;
        border-radius: 8px;
        padding: 22px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
    }
    .rec-box {
        background: #f8fafc;
        border-right: 5px solid #2563eb;
        padding: 16px;
        border-radius: 8px;
        margin-top: 15px;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# قواعد البيانات الجغرافية ودوال التحميل التلقائي
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

    def __getitem__(self, key):
        return getattr(self, key)
    
    def get(self, key, default=None):
        return getattr(self, key, default)

@st.cache_data
def load_cities():
    gc = geonamescache.GeonamesCache()
    cities_list = []
    for city_id, city_data in gc.get_cities().items():
        if city_data.get("population", 0) >= 15000:
            cities_list.append(
                City(
                    geonameid=city_id,
                    name=city_data.get("name", ""),
                    country_code=city_data.get("countrycode", ""),
                    latitude=city_data.get("latitude", 0.0),
                    longitude=city_data.get("longitude", 0.0),
                    admin1=city_data.get("admin1code", ""),
                    population=city_data.get("population", 0),
                )
            )
    return cities_list

@st.cache_data
def load_countries():
    gc = geonamescache.GeonamesCache()
    return gc.get_countries()

@st.cache_data
def load_geo_data():
    countries = load_countries()
    cities = load_cities()

    country_map = {c["name"]: code for code, c in countries.items()}
    sorted_countries = sorted(list(country_map.keys()))

    cities_by_country = {}
    for c_code in country_map.values():
        c_cities = [
            city for city in cities if city.country_code == c_code
        ]
        c_cities_sorted = sorted(
            c_cities, key=lambda x: x.population, reverse=True
        )
        cities_by_country[c_code] = c_cities_sorted

    return country_map, sorted_countries, cities_by_country

country_map, country_list, cities_by_country = load_geo_data()
tf = TimezoneFinder()

# =============================================================================
# المعاجم الفلكية والكرامات الأساسية
# =============================================================================
ZODIAC_NAMES_AR = [
    "الحمل", "الثور", "الجوزاء", "السرطان",
    "الأسد", "العذراء", "الميزان", "العقرب",
    "القوس", "الجدي", "الدلو", "الحوت"
]

PLANET_NAMES_AR = {
    "Sun": "الشمس",
    "Moon": "القمر",
    "Mercury": "عطارد",
    "Venus": "الزهرة",
    "Mars": "المريخ"
}

PLANET_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS
}

SIGN_RULERS = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
    4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
    8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

EXALTATIONS = {
    "Sun": 0,     # الحمل
    "Moon": 1,    # الثور
    "Mercury": 5, # العذراء
    "Venus": 11,  # الحوت
    "Mars": 9     # الجدي
}

DETRIMENTS = {
    "Sun": 10,          # الدلو
    "Moon": 9,          # الجدي
    "Mercury": [8, 11], # القوس والحوت
    "Venus": [0, 7],    # الحمل والعقرب
    "Mars": [1, 6]      # الثور والميزان
}

FALLS = {
    "Sun": 6,     # الميزان
    "Moon": 7,    # العقرب
    "Mercury": 11,# الحوت
    "Venus": 5,   # العذراء
    "Mars": 3     # السرطان
}

# =============================================================================
# دوال الحسابات الفلكية وتقييم القوى
# =============================================================================
def angular_diff(lon1, lon2):
    diff = abs(lon1 - lon2) % 360
    return min(diff, 360 - diff)

def get_aspect_between(lon1, lon2):
    dist = angular_diff(lon1, lon2)
    if dist <= 8.0:
        return "اقتران (0°)"
    if abs(dist - 60.0) <= 6.0:
        return "تسديس (60°)"
    if abs(dist - 90.0) <= 6.0:
        return "تربيع (90°)"
    if abs(dist - 120.0) <= 6.0:
        return "تثليث (120°)"
    if abs(dist - 180.0) <= 6.0:
        return "مقابلة (180°)"
    return None

def evaluate_personal_planet_score(planet_name, planet_lon, personal_planets_data, use_house_weight=False):
    score = 2.0  
    reasons = ["نقطة الأساس: 2.0"]
    p_entry = personal_planets_data[planet_name]
    sign_idx = int(planet_lon / 30) % 12
    house_num = p_entry["whole_sign_house"]

    # 1. الحظوظ الذاتية (البيت والشرف)
    if SIGN_RULERS.get(sign_idx) == planet_name:
        score += 1.5
        reasons.append("في بيته (+1.5)")
    elif EXALTATIONS.get(planet_name) == sign_idx:
        score += 2.0
        reasons.append("في شرفه (+2.0)")

    # 2. الانتكاسات الذاتية (الوبال والهبوط مع منع التصفير المزدوج غير المتوازن لعطارد في الحوت)
    det_val = DETRIMENTS.get(planet_name)
    is_detriment = (isinstance(det_val, list) and sign_idx in det_val) or (det_val == sign_idx)
    is_fall = (FALLS.get(planet_name) == sign_idx)

    if is_detriment and is_fall:
        score -= 1.75
        reasons.append("في وباله وهبوطه معاً (-1.75)")
    else:
        if is_detriment:
            score -= 1.0
            reasons.append("في وباله (-1.0)")
        if is_fall:
            score -= 1.5
            reasons.append("في هبوطه (-1.5)")

    # 3. وزن البيوت الفلكية (الأوتاد والمثلثات الصالحة مقابل البيوت الساقطة) عند توفر ساعة الميلاد
    if use_house_weight:
        if house_num in [1, 4, 7, 10]:
            score += 0.5
            reasons.append(f"في بيت وتد [البيت {house_num}] (+0.5)")
        elif house_num in [5, 9, 11]:
            score += 0.25
            reasons.append(f"في بيت سعيد [البيت {house_num}] (+0.25)")
        elif house_num in [6, 8, 12]:
            score -= 0.5
            reasons.append(f"في بيت ساقط [البيت {house_num}] (-0.5)")

    # 4. الاتصالات الفلكية بين الكواكب الشخصية
    for other_p, other_data in personal_planets_data.items():
        if other_p == planet_name:
            continue
        asp = get_aspect_between(planet_lon, other_data['lon'])
        if not asp:
            continue

        other_ar = PLANET_NAMES_AR[other_p]

        if asp in ["تثليث (120°)", "تسديس (60°)"]:
            score += 0.75
            reasons.append(f"{asp} مع {other_ar} (+0.75)")
        elif asp == "اقتران (0°)":
            if other_p == "Mars" and planet_name != "Mars":
                score -= 0.75
                reasons.append(f"اقتران مع {other_ar} (-0.75)")
            else:
                score += 0.75
                reasons.append(f"اقتران مع {other_ar} (+0.75)")
        elif asp in ["تربيع (90°)", "مقابلة (180°)"]:
            if other_p == "Mars":
                score -= 1.0
                reasons.append(f"{asp} مع {other_ar} (-1.0)")
            else:
                score -= 0.5
                reasons.append(f"{asp} مع {other_ar} (-0.5)")

    final_score = round(min(5.0, max(0.0, score)), 1)
    return final_score, reasons

def get_strength_label(score):
    if score >= 3.0:
        return "قوي", "🟢"
    elif score > 1.0:
        return "متوسط", "🟡"
    else:
        return "ضعيف", "🔴"

# =============================================================================
# دالة تقديم الحلول والعلاجات الفلكية المتقدمة وفق أحدث مراجع التنجيم الغربي الحديث
# =============================================================================
def get_advanced_recommendations(gender, venus_sc, moon_sc, sun_sc, mars_sc, fem_power, masc_power):
    recommendations = []
    
    is_venus_strong = venus_sc >= 3.0
    is_moon_strong = moon_sc >= 3.0
    is_sun_strong = sun_sc >= 3.0
    is_mars_strong = mars_sc >= 3.0
    
    if gender == "أنثى":
        if is_venus_strong and is_moon_strong and (fem_power > masc_power):
            recommendations.append("✨ **حالة متوازنة وممتازة:** لا تحتاجين إلى نصائح إضافية، فطاقة الأنوثة والقمر والزهرة في أعلى مستويات التناغم الداخلي والخارجي وفقاً لدلائل التنجيم الحديث.")
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
            recommendations.append("👑 **حالة ذكورية قيادية متوازنة:** لا تحتاج إلى نصائح إضافية، فطاقة الشمس والمريخ تدعمك بكفاءة عالية للقيادة وتحمل المسؤولية والإنجاب.")
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
# مولد تقرير HTML الاحترافي للطباعة والتحميل
# =============================================================================
def generate_html_report(data):
    planets_rows = ""
    for p_name in ["Sun", "Moon", "Mercury", "Venus", "Mars"]:
        p_info = data["planets_data"][p_name]
        sc = data["scores"][p_name]
        reasons_txt = " | ".join(data["reasons"][p_name])
        lbl, icon = get_strength_label(sc)
        badge_style = (
            "background:#dcfce7; color:#166534;" if sc >= 3.0
            else ("background:#fef9c3; color:#854d0e;" if sc > 1.0 else "background:#fee2e2; color:#991b1b;")
        )
        planets_rows += f"""
        <tr>
            <td style="font-weight:700;">{PLANET_NAMES_AR[p_name]}</td>
            <td>{p_info['sign_name']} ({p_info['deg_in_sign']:.1f}°)</td>
            <td style="text-align:center;">البيت {p_info['whole_sign_house']}</td>
            <td style="text-align:center; font-weight:800;">{sc} / 5</td>
            <td style="text-align:center;"><span style="padding:4px 10px; border-radius:12px; font-weight:700; font-size:12px; {badge_style}">{icon} {lbl}</span></td>
            <td style="font-size:12px; color:#475569;">{reasons_txt}</td>
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
    <title>تقرير صلاحية الزواج الفلكي المتقدم - {data['name']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@700&family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Cairo', sans-serif;
            direction: rtl;
            text-align: right;
            background: #f8fafc;
            color: #1e293b;
            padding: 30px;
            margin: 0;
            font-size: 14px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: #ffffff;
            padding: 35px;
            border-radius: 14px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        }}
        .header {{
            text-align: center;
            background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 100%);
            color: #f1f5f9;
            padding: 25px;
            border-radius: 12px;
            border: 2px solid #c59b27;
            margin-bottom: 25px;
        }}
        .header h1 {{
            font-family: 'Amiri', serif;
            color: #e6ca65;
            font-size: 28px;
            margin: 0 0 6px 0;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 800;
            color: #0d1b2a;
            border-bottom: 2px solid #c59b27;
            padding-bottom: 8px;
            margin: 22px 0 14px 0;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        .info-box {{
            background: #f8fafc;
            padding: 12px 15px;
            border-radius: 8px;
            border-right: 4px solid #c59b27;
            border: 1px solid #e2e8f0;
        }}
        .info-box span {{
            display: block;
            font-size: 12px;
            color: #64748b;
        }}
        .info-box strong {{
            font-size: 14px;
            color: #0d1b2a;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th {{
            background: #1a2a44;
            color: #ffffff;
            padding: 10px 12px;
            text-align: right;
            font-weight: 700;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .power-summary {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 18px;
        }}
        .power-card {{
            background: #fcf8e8;
            border: 1px solid #fde68a;
            border-radius: 8px;
            padding: 14px;
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
            font-size: 19px;
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
            line-height: 1.9;
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
            .container {{ box-shadow: none; border: none; padding: 10px; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>تقرير صلاحية الزواج الفلكي المتقدم</h1>
        <p>دراسة صلاحية الكواكب الشخصية للزواج وفق نظام كل برج بيت - استرو رادار</p>
    </div>

    <div class="section-title">البيانات الأساسية</div>
    <div class="info-grid">
        <div class="info-box"><span>الاسم</span><strong>{data['name']}</strong></div>
        <div class="info-box"><span>الجنس</span><strong>{data['gender']}</strong></div>
        <div class="info-box"><span>تاريخ وساعة الميلاد</span><strong>{data['birth_date']} ({data['birth_time_label']})</strong></div>
        <div class="info-box"><span>موقع الولادة والطالع</span><strong>{data['location']} ({data['asc_label']})</strong></div>
    </div>

    <div class="section-title">تقييم الكواكب الشخصية الخمسة (من 5 نقاط)</div>
    <table>
        <thead>
            <tr>
                <th>الكوكب</th>
                <th>البرج والدرجة</th>
                <th style="text-align:center;">البيت (كل برج بيت)</th>
                <th style="text-align:center;">الدرجة</th>
                <th style="text-align:center;">التصنيف</th>
                <th>تفاصيل الكرامات والاتصالات الفلكية</th>
            </tr>
        </thead>
        <tbody>
            {planets_rows}
        </tbody>
    </table>

    <div class="section-title">مقارنة الكتل الطاقية (الأنوثة مقابل الذكورة)</div>
    <div class="power-summary">
        <div class="power-card">
            <div style="font-size:13px; color:#64748b;">مجموع طاقة الأنوثة (الزهرة + القمر)</div>
            <div style="font-size:22px; font-weight:900; color:#be185d;">{data['fem_power']:.1f} نقطة</div>
        </div>
        <div class="power-card">
            <div style="font-size:13px; color:#64748b;">مجموع طاقة الذكورة (الشمس + المريخ)</div>
            <div style="font-size:22px; font-weight:900; color:#1d4ed8;">{data['masc_power']:.1f} نقطة</div>
        </div>
    </div>

    <div class="mercury-box">
        🧠 <strong>حالة كوكب عطارد ({data['mercury_score']} / 5 — {data['mercury_label']}):</strong> {data['mercury_text']}
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
        <p>تقرير صادر آلياً — نظام كل برج بيت (Whole Sign) وموقع جغرافية الحدث وتوقيت الميلاد ودلائل التنجيم الحديث — استرو رادار</p>
    </div>
</div>
</body>
</html>
"""
    return html

# =============================================================================
# واجهة المستخدم في Streamlit (الشريط الجانبي والواجهة الرئيسية)
# =============================================================================
st.markdown("""
<div class="main-header">
    <h1>حاسبة صلاحية الزواج الفلكية المتقدمة</h1>
    <p>تقييم الكواكب الشخصية للزواج و تحديد الحلول و الإرشادات الفلكية بناءً على أحدث مراجع التنجيم - استرو رادار</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("👤 بيانات الشخص")
    name = st.text_input("الاسم", "سارة")
    gender = st.selectbox("الجنس", ["أنثى", "ذكر"], index=0)
    birth_date = st.date_input("تاريخ الميلاد", value=datetime.date(2010, 1, 1), min_value=datetime.date(1950, 1, 1))

    st.markdown("---")
    st.header("⏰ توقيت الميلاد")
    time_option = st.radio("معرفة ساعة الميلاد:", ["عدم معرفة ساعة الميلاد", "معرفة ساعة الميلاد"])
    
    birth_time_obj = datetime.time(12, 0)
    if time_option == "معرفة ساعة الميلاد":
        birth_time_str = st.text_input("أدخل ساعة الميلاد (بتنسيق HH:MM):", value="14:30")
        try:
            parts = list(map(int, birth_time_str.split(":")))
            h = parts[0]
            m = parts[1] if len(parts) > 1 else 0
            s = parts[2] if len(parts) > 2 else 0
            birth_time_obj = datetime.time(h, m, s)
        except Exception:
            st.warning("⚠️ تنسيق الوقت غير صحيح، سيتم افتراض الساعة 12:00 بالمنتصف.")
            birth_time_obj = datetime.time(12, 0)

    st.markdown("---")
    st.header("🌍 موقع الولادة الجغرافي")
    selected_country_name = st.selectbox("اختر الدولة:", country_list)
    country_code = country_map[selected_country_name]
    country_cities = cities_by_country.get(country_code, [])
    city_names = [c.name for c in country_cities]

    if city_names:
        selected_city_name = st.selectbox("اختر المدينة:", city_names)
        selected_city = next((c for c in country_cities if c.name == selected_city_name), country_cities[0])
        lat = selected_city.latitude
        lon = selected_city.longitude
        location_label = f"{selected_city_name}, {selected_country_name}"
    else:
        lat, lon = 25.2048, 55.2708
        location_label = selected_country_name

    tz_str = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    st.info(f"📍 الإحداثيات: {lat:.2f}°, {lon:.2f}°\n\n⏰ المنطقة الزمنية: `{tz_str}`")

submit = st.button("🔮 تنفيذ التحليل الفلكي الشامل وتوليد التقرير", type="primary")

if submit:
    # حساب التوقيت العالمي (UTC) واليوم اليولياني بدقة تامة
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

    raw_lons = {}
    for p_name, p_id in PLANET_IDS.items():
        res = swe.calc_ut(jd, p_id)
        raw_lons[p_name] = res[0][0]

    # نظام كل برج بيت: إذا توفرت ساعة الميلاد يتم حساب برج الطالع كبداية للبيت الأول، وإلا فيعتمد برج الشمس
    if has_birth_time:
        houses_cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W')
        asc_lon = ascmc[0]
        house_start_sign = int(asc_lon / 30) % 12
        asc_label = f"الطالع: {ZODIAC_NAMES_AR[house_start_sign]} ({asc_lon % 30:.1f}°)"
    else:
        house_start_sign = int(raw_lons["Sun"] / 30) % 12
        asc_label = f"طالع شمسي: {ZODIAC_NAMES_AR[house_start_sign]}"

    planets_data = {}
    for p_name, p_lon in raw_lons.items():
        sign_idx = int(p_lon / 30) % 12
        whole_sign_house = ((sign_idx - house_start_sign) % 12) + 1
        planets_data[p_name] = {
            "lon": p_lon,
            "sign_idx": sign_idx,
            "sign_name": ZODIAC_NAMES_AR[sign_idx],
            "deg_in_sign": p_lon % 30,
            "whole_sign_house": whole_sign_house
        }

    scores = {}
    reasons = {}
    for p_name in ["Sun", "Moon", "Mercury", "Venus", "Mars"]:
        sc, r_list = evaluate_personal_planet_score(
            p_name,
            planets_data[p_name]["lon"],
            planets_data,
            use_house_weight=has_birth_time
        )
        scores[p_name] = sc
        reasons[p_name] = r_list

    st.markdown("---")
    st.markdown(f"### 📊 نتائج تحليل الكواكب الشخصية لـ ({name}) — الجنس: ({gender}) — الموقع: ({location_label})")

    col_res1, col_res2 = st.columns([1.3, 1])
    with col_res1:
        st.markdown("#### ⭐ درجات الكواكب الشخصية (من 5 نقاط):")
        for p_name in ["Sun", "Moon", "Mercury", "Venus", "Mars"]:
            sc = scores[p_name]
            lbl, icon = get_strength_label(sc)
            p_info = planets_data[p_name]
            st.write(f"- **{PLANET_NAMES_AR[p_name]}**: `{sc} / 5` [{icon} **{lbl}**] — برج {p_info['sign_name']} (البيت {p_info['whole_sign_house']})")
            st.caption(f"    التفاصيل: {' | '.join(reasons[p_name])}")

    with col_res2:
        st.markdown("#### ℹ️ المنهجية الفلكية المعتمدة:")
        st.info(
            f"- **ساعة الميلاد:** {'معروفة (' + str(birth_time_obj) + ')' if has_birth_time else 'غير معروفة (تقدير منتصف النهار المحلي)'}\n"
            f"- **مرجعية البيوت:** {asc_label} (نظام كل برج بيت Whole Sign).\n"
            "- **تقدير القمر والكواكب:** محسوبة رياضياً عبر خوارزمية Swiss Ephemeris بدقة تامة.\n"
            "- **المقياس:** 3 فأكثر = قوي | 2 = متوسط | 1 فأقل = ضعيف."
        )

    sun_sc = scores["Sun"]
    moon_sc = scores["Moon"]
    mercury_sc = scores["Mercury"]
    venus_sc = scores["Venus"]
    mars_sc = scores["Mars"]

    is_sun_strong = sun_sc >= 3.0
    is_moon_strong = moon_sc >= 3.0
    is_mercury_strong = mercury_sc >= 3.0
    is_venus_strong = venus_sc >= 3.0
    is_mars_strong = mars_sc >= 3.0

    fem_power = round(venus_sc + moon_sc, 1)
    masc_power = round(sun_sc + mars_sc, 1)

    st.markdown("---")
    st.markdown("### ⚖️ موازين القوى والتشخيص النهائي:")
    c_p1, c_p2 = st.columns(2)
    c_p1.metric("مجموع طاقة الأنوثة (الزهرة + القمر)", f"{fem_power} نقطة")
    c_p2.metric("مجموع طاقة الذكورة (الشمس + المريخ)", f"{masc_power} نقطة")

    mercury_lbl, _ = get_strength_label(mercury_sc)
    if is_mercury_strong:
        mercury_text = "عطارد قوي (جيد جداً للجنسين): يدل على رجاحة العقل، سرعة الفهم، وحسن التواصل والحوار لحل الخلافات الزوجية."
        st.success(f"🟢 **{mercury_text}**")
    else:
        mercury_text = f"عطارد {mercury_lbl}: التواصل الفكري والحوار يحتاجان إلى صبر ووضوح لتجنب سوء الفهم."
        st.warning(f"🟡 **{mercury_text}**")

    # =========================================================================
    # التشخيص وشروط الأنثى والذكر
    # =========================================================================
    diag_title = ""
    diag_summary = ""
    diag_bullets = []
    border_color = "#c59b27"
    bg_tint = "#ffffff"
    title_color = "#0d1b2a"

    if gender == "أنثى":
        if fem_power <= masc_power:
            diag_title = "❌ لا تصلح للزواج لأن طاقة الذكورة مرتفعة"
            diag_summary = f"مجموع الزهرة والقمر ({fem_power}) ≤ مجموع الشمس والمريخ ({masc_power}):"
            diag_bullets = [
                "طاقة الذكورة والسيطرة والاستقلالية تطغى على الطبيعة الأنثوية.",
                "يصعب عليها التكيف مع متطلبات الزواج التقليدي أو الخضوع لسلطة الزوج، مما يولد صداماً مستمراً."
            ]
            border_color = "#ef4444"
            bg_tint = "#fef2f2"
            title_color = "#991b1b"

        elif is_venus_strong and is_moon_strong and (fem_power > masc_power):
            diag_title = "✅ تصلح للزواج، الإنجاب، رعاية الأطفال، التدبير المنزلي، والأنوثة"
            diag_summary = f"زهرة قوية ({venus_sc}) + قمر قوي ({moon_sc}) + (الزهرة + القمر > الشمس + المريخ):"
            diag_bullets = [
                "أنوثة مكتملة: الاهتمام بالجسد والزينة والعناية بالمظهر.",
                "أمومة واعية: قدرة عالية على رعاية الأطفال وتربيتهم بحنان وعاطفة صادقة.",
                "ربة منزل بارعة: إتقان التدبير المنزلي وإشاعة الدفء والاستقرار في عش الزوجية."
            ]
            border_color = "#16a34a"
            bg_tint = "#f0fdf4"
            title_color = "#166534"

        elif is_moon_strong and (venus_sc < 3.0) and (fem_power > masc_power):
            diag_title = "🟡 تنفع للإنجاب، رعاية الأطفال، والتدبير المنزلي فقط"
            diag_summary = f"قمر قوي ({moon_sc}) + زهرة ضعيفة ({venus_sc}) + (الزهرة + القمر > الشمس + المريخ):"
            diag_bullets = [
                "مؤهلة تماماً للإنجاب، رعاية الأطفال، وتدبير شؤون المنزل بمسؤولية وعملية عالية.",
                "يقل اهتمامها بالزينة الشكلية والمتع الحسية، حيث يكون تركيزها الأساسي منصباً على واجبات الأمومة والاستقرار العائلي."
            ]
            border_color = "#d97706"
            bg_tint = "#fffbeb"
            title_color = "#92400e"

        elif is_venus_strong and (moon_sc < 3.0) and (fem_power > masc_power):
            diag_title = "💖 طاقة أنوثة (تصلح لزواج لا يحتاج أطفالاً أو تدبيراً منزلياً بل للمتعة الحسية فقط)"
            diag_summary = f"زهرة قوية ({venus_sc}) + قمر ضعيف ({moon_sc}) + (الزهرة + القمر > الشمس + المريخ):"
            diag_bullets = [
                "طاقة أنوثة طاغية وجاذبية حسية عالية مكرسة للجمال والزينة والعلاقة العاطفية المتبادلة.",
                "تصلح لزواج رفقة ومتعة حسية فقط، ولا تتوافق مع أعباء الإنجاب أو رعاية الأطفال أو التدبير المنزلي."
            ]
            border_color = "#db2777"
            bg_tint = "#fdf2f8"
            title_color = "#9d174d"

        else:
            diag_title = "🟡 صلاحية متوسطة للزواج (طاقة أنوثة معتدلة)"
            diag_summary = f"مجموع الزهرة والقمر ({fem_power}) أكبر من الشمس والمريخ ({masc_power}) بقيم متوسطة:"
            diag_bullets = [
                "تؤدي الواجبات الزوجية والمنزلية بصورة معتدلة ودون تفوق استثنائي في مجال محدد."
            ]
            border_color = "#2563eb"
            bg_tint = "#eff6ff"
            title_color = "#1e40af"

    else:
        if (masc_power <= fem_power) or (sun_sc < 3.0 and mars_sc < 3.0):
            diag_title = "❌ لا يصلح للزواج"
            diag_summary = f"مجموع (الشمس {sun_sc} + المريخ {mars_sc} = {masc_power}) ≤ (القمر + الزهرة {fem_power}) أو كلاهما ضعيفان (< 3.0):"
            diag_bullets = [
                "ضعف في مقومات القيادة وتحمل المسؤولية الزوجية والمادية.",
                "تغلب عليه الحساسية أو التردد، مما يجعله غير مؤهل للزواج وتحمل أعباء الأسرة."
            ]
            border_color = "#ef4444"
            bg_tint = "#fef2f2"
            title_color = "#991b1b"

        else:
            if is_sun_strong and is_mars_strong and (abs(sun_sc - mars_sc) <= 0.5):
                diag_title = "👑 يصلح للزواج والقيادة والعمل الشاق والإنجاب بامتياز"
                diag_summary = f"الشمس والمريخ كلاهما قويان ومتساويان (الشمس: {sun_sc}، المريخ: {mars_sc}):"
                diag_bullets = [
                    "يجمع ببراعة بين هيبة القيادة وإدارة شؤون المنزل (الشمس) وبين القوة البدنية والعمل الشاق وإنجاب الأطفال (المريخ)."
                ]
                border_color = "#16a34a"
                bg_tint = "#f0fdf4"
                title_color = "#166534"

            elif is_sun_strong and (mars_sc < 3.0):
                diag_title = "👔 يصلح للزواج، لكن لا يصلح للعمل الشاق أو التصليح في المنزل أو لإنجاب الأطفال"
                diag_summary = f"الشمس قوية ({sun_sc}) + المريخ ضعيف ({mars_sc}):"
                diag_bullets = [
                    "يصلح للزواج والوجاهة والقيادة واتخاذ القرارات الإدارية.",
                    "لا يصلح للأعمال البدنية الشاقة، صيانة أو تصليح مرافق المنزل، أو إنجاب الأطفال."
                ]
                border_color = "#d97706"
                bg_tint = "#fffbeb"
                title_color = "#92400e"

            elif is_mars_strong and (sun_sc < 3.0):
                diag_title = "🛠️ يصلح لإنجاب الأطفال والعمل الشاق وتصليح المنزل، لكن غير جيد لقيادة شؤون المنزل وتحمل كامل مسؤوليته"
                diag_summary = f"المريخ قوي ({mars_sc}) + الشمس ضعيفة ({sun_sc}):"
                diag_bullets = [
                    "يتمتع بطاقة جسدية عالية تجعله صالحاً لإنجاب الأطفال، العمل الشاق، والصيانة المنزلية.",
                    "غير جيد لقيادة شؤون الأسرة الإدارية أو التخطيط الاستراتيجي وتحمل كامل المسؤولية المعنوية."
                ]
                border_color = "#2563eb"
                bg_tint = "#eff6ff"
                title_color = "#1e40af"

            else:
                diag_title = "⚖️ يصلح للزواج بشكل عام (قوى ذكورية متوازنة)"
                diag_summary = f"مجموع الذكورة ({masc_power}) أكبر من الأنوثة مع قوى متباينة نسبياً (الشمس: {sun_sc}، المريخ: {mars_sc}):"
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

    # توليد التوصيات المتقدمة والعلاجات الفلكية الطبيعية
    recommendations = get_advanced_recommendations(gender, venus_sc, moon_sc, sun_sc, mars_sc, fem_power, masc_power)
    
    st.markdown("""
    <div class="rec-box">
        <h3>💡 التوصيات والإرشادات العملية وعلاجات تقوية الكواكب فلكياً (وفق أحدث المراجع):</h3>
    </div>
    """, unsafe_allow_html=True)
    for rec in recommendations:
        if rec.startswith(("✨", "🏡", "💖", "🛠️", "👑", "👔", "🔥", "☀️", "🚀", "🌙", "🌹", "🌸", "⚡")):
            st.markdown(f"#### {rec}")
        else:
            st.markdown(f"- {rec}")

    # إعداد البيانات لتصدير تقرير الـ HTML
    report_payload = {
        "name": name,
        "gender": gender,
        "birth_date": birth_date.strftime("%Y-%m-%d"),
        "birth_time_label": str(birth_time_obj) if has_birth_time else "غير محددة",
        "location": location_label,
        "asc_label": asc_label,
        "planets_data": planets_data,
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
        label=f"📥 تحميل تقرير التحليل الفلكي الشامل لـ ({name}) [HTML للطباعة]",
        data=html_report,
        file_name=f"تقرير_التوافق_الفلكي_{name.replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True
    )
