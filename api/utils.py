import statistics
from dataclasses import dataclass
from typing import Any, TypeVar, Type, cast


T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class Vitals:
    ox: int
    hr: int
    mv: int
    sc: int
    st: int
    bso: int
    bat: int
    btt: int
    chg: int
    aps: int
    alrt: int
    ota: int
    srf: int
    rsi: int
    sb: int
    ss: int
    mvb: int
    mst: int
    oxta: int
    onm: int
    bsb: int
    mrs: int
    bp: int
    hw: str

    @staticmethod
    def from_dict(obj: Any) -> 'Vitals':
        assert isinstance(obj, dict)
        ox = from_int(obj.get("ox"))
        hr = from_int(obj.get("hr"))
        mv = from_int(obj.get("mv"))
        sc = from_int(obj.get("sc"))
        st = from_int(obj.get("st"))
        bso = from_int(obj.get("bso"))
        bat = from_int(obj.get("bat"))
        btt = from_int(obj.get("btt"))
        chg = from_int(obj.get("chg"))
        aps = from_int(obj.get("aps"))
        alrt = from_int(obj.get("alrt"))
        ota = from_int(obj.get("ota"))
        srf = from_int(obj.get("srf"))
        rsi = from_int(obj.get("rsi"))
        sb = from_int(obj.get("sb"))
        ss = from_int(obj.get("ss"))
        mvb = from_int(obj.get("mvb"))
        mst = from_int(obj.get("mst"))
        oxta = from_int(obj.get("oxta"))
        onm = from_int(obj.get("onm"))
        bsb = from_int(obj.get("bsb"))
        mrs = from_int(obj.get("mrs"))
        bp = from_int(obj.get("bp"))
        hw = from_str(obj.get("hw"))
        return Vitals(ox, hr, mv, sc, st, bso, bat, btt, chg, aps, alrt, ota, srf, rsi, sb, ss, mvb, mst, oxta, onm, bsb, mrs, bp, hw)

    def to_dict(self) -> dict:
        result: dict = {}
        result["ox"] = from_int(self.ox)
        result["hr"] = from_int(self.hr)
        result["mv"] = from_int(self.mv)
        result["sc"] = from_int(self.sc)
        result["st"] = from_int(self.st)
        result["bso"] = from_int(self.bso)
        result["bat"] = from_int(self.bat)
        result["btt"] = from_int(self.btt)
        result["chg"] = from_int(self.chg)
        result["aps"] = from_int(self.aps)
        result["alrt"] = from_int(self.alrt)
        result["ota"] = from_int(self.ota)
        result["srf"] = from_int(self.srf)
        result["rsi"] = from_int(self.rsi)
        result["sb"] = from_int(self.sb)
        result["ss"] = from_int(self.ss)
        result["mvb"] = from_int(self.mvb)
        result["mst"] = from_int(self.mst)
        result["oxta"] = from_int(self.oxta)
        result["onm"] = from_int(self.onm)
        result["bsb"] = from_int(self.bsb)
        result["mrs"] = from_int(self.mrs)
        result["bp"] = from_int(self.bp)
        result["hw"] = from_str(self.hw)
        return result


def vitals_from_dict(s: Any) -> Vitals:
    return Vitals.from_dict(s)


def vitals_to_dict(x: Vitals) -> Any:
    return to_class(Vitals, x)


@dataclass
class BabyMetrics:
    stress_level: float  # 0-100%
    sleep_quality: float  # 0-100%
    breathing_status: str  # 'Normal', 'Check', 'Alert'
    activity_level: str  # 'Sleeping', 'Active', 'Very Active'
    overall_health: float  # 0-100%


class VitalsAnalyzer:
    # Rangos normales para bebés
    NORMAL_HR_RANGE = (80, 160)  # Ritmo cardíaco normal en bebés
    NORMAL_OX_RANGE = (95, 100)  # Saturación de oxígeno normal

    def __init__(self, history_size: int = 10):
        self.history_size = history_size
        self.hr_history = []
        self.ox_history = []
        self.mv_history = []

    def add_measurement(self, vitals: Vitals) -> BabyMetrics:
        """Analiza nuevas mediciones y calcula métricas"""
        # Actualizar históricos
        self.hr_history.append(vitals.hr)
        self.ox_history.append(vitals.ox)
        self.mv_history.append(vitals.mv)

        # Mantener solo el histórico reciente
        self.hr_history = self.hr_history[-self.history_size:]
        self.ox_history = self.ox_history[-self.history_size:]
        self.mv_history = self.mv_history[-self.history_size:]

        return BabyMetrics(
            stress_level=self._calculate_stress_level(),
            sleep_quality=self._calculate_sleep_quality(),
            breathing_status=self._assess_breathing_status(),
            activity_level=self._determine_activity_level(),
            overall_health=self._calculate_overall_health()
        )

    def _calculate_stress_level(self) -> float:
        """Calcula nivel de estrés basado en variabilidad del ritmo cardíaco"""
        if len(self.hr_history) < 2:
            return 0.0

        hr_variability = statistics.stdev(self.hr_history)
        hr_mean = statistics.mean(self.hr_history)

        # Alta variabilidad o ritmo cardíaco elevado indica estrés
        stress = 0.0
        if hr_mean > self.NORMAL_HR_RANGE[1]:
            stress += 50

        # Normalizar la variabilidad a una escala de 0-50
        stress += min(50, (hr_variability / 10) * 50)

        return min(100, stress)

    def _calculate_sleep_quality(self) -> float:
        """Evalúa la calidad del sueño basado en movimiento y estabilidad de signos vitales"""
        if not self.mv_history:
            return 0.0

        # Menos movimiento indica mejor sueño
        movement_score = 100 - (sum(self.mv_history) / len(self.mv_history)) * 100

        # Estabilidad en ritmo cardíaco indica mejor sueño
        hr_stability = 100
        if len(self.hr_history) >= 2:
            hr_variability = statistics.stdev(self.hr_history)
            hr_stability = max(0, 100 - (hr_variability * 2))

        return (movement_score + hr_stability) / 2

    def _assess_breathing_status(self) -> str:
        """Evalúa el estado respiratorio basado en oxigenación"""
        if not self.ox_history:
            return 'Unknown'

        current_ox = self.ox_history[-1]

        if current_ox >= self.NORMAL_OX_RANGE[0]:
            return 'Normal'
        elif current_ox >= 90:
            return 'Check'
        else:
            return 'Alert'

    def _determine_activity_level(self) -> str:
        """Determina nivel de actividad basado en movimiento"""
        if not self.mv_history:
            return 'Unknown'

        recent_movement = statistics.mean(self.mv_history[-3:])

        if recent_movement < 0.3:
            return 'Sleeping'
        elif recent_movement < 0.7:
            return 'Active'
        else:
            return 'Very Active'

    def _calculate_overall_health(self) -> float:
        """Calcula índice general de salud"""
        if not (self.ox_history and self.hr_history):
            return 0.0

        current_ox = self.ox_history[-1]
        current_hr = self.hr_history[-1]

        # Evaluar oxigenación (60% del índice)
        ox_score = max(0, min(100, (current_ox - 90) * 10)) * 0.6

        # Evaluar ritmo cardíaco (40% del índice)
        hr_score = 100
        if current_hr < self.NORMAL_HR_RANGE[0]:
            hr_score = (current_hr / self.NORMAL_HR_RANGE[0]) * 100
        elif current_hr > self.NORMAL_HR_RANGE[1]:
            hr_score = max(0, 100 - ((current_hr - self.NORMAL_HR_RANGE[1]) / 10))
        hr_score *= 0.4

        return ox_score + hr_score

