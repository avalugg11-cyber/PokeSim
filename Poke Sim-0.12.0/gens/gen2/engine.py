"""Gen 2 (Crystal) 1v1 battle engine (v0.1). Side A is the "player" (Johto badge boosts), side B the "enemy"."""
from .base import *
from .effects import Effects

class Battle(Effects):
    def __init__(self, sa, sb, rng, brain, rules=RULES, log=None):
        self.weather, self.weather_left = None, 0
        self.a, self.b = fresh(sa, self, True), fresh(sb, self, False)
        self.rnd = rng.getrandbits
        self.brain, self.rules, self.log = brain, rules, log
        self.res, self.turn, self.actor = None, 0, None

    def pick(self, m, o):
        if m.recharge:
            return (None, -1, "recharge")
        if m.charge is not None:
            return (m.charge, -1, "charge2")
        if m.rampage_left > 0:
            return (m.rampage_mv, -1, "rampage")
        if m.rollout_left > 0:
            return (m.rampage_mv, -1, "rollout")
        if m.bide_left > 0:
            return (MV["BIDE"], -1, "bide")
        if m.encore_left > 0 and m.encore_mv in m.moves:
            i = m.moves.index(m.encore_mv)
            if m.pp[i] > 0:
                return (m.encore_mv, i, "normal")
        mv, idx = self.brain(m, o)
        return (mv, idx, "normal")

    def run(self):
        a, b, rnd = self.a, self.b, self.rnd
        for t in range(1, self.rules.turn_limit + 1):
            self.turn = t
            for m in (a, b):
                m.flinch, m.took_dmg, m.took_phys = False, 0, None
            ca, cb = self.pick(a, b), self.pick(b, a)
            # Reset at selection, before a faster opponent can build the old Rage.
            for m, c in ((a, ca), (b, cb)):
                if c[2] == "normal" and c[0] is not None and c[0].effect != "RAGE":
                    m.rage, m.rage_n = False, 1
            pa = ca[0].prio if ca[0] else 0
            pb = cb[0].prio if cb[0] else 0
            if pa != pb:
                a_first = pa > pb
            else:
                sa, sb = spd(a), spd(b)
                a_first = (rnd(8) < 128) if sa == sb else sa > sb
            order = ((a, b, ca), (b, a, cb)) if a_first else ((b, a, cb), (a, b, ca))
            for m, o, c in order:
                self.actor = m
                self.act(m, o, *c)
                if self.over():
                    return self.res
            if self.between_turns((order[0][0], order[1][0])):
                return self.res
        self.res = 2
        return 2

    def can_move(self, m, o, mv, idx):
        rnd = self.rnd
        if m.status == SLP:
            m.slp -= 1
            if m.slp <= 0:
                m.status, m.nightmare = 0, False          
            elif mv.effect not in ("SNORE", "SLEEP_TALK"):
                return False
        if m.status == FRZ:
            if mv.name in ("FLAME_WHEEL", "SACRED_FIRE") or rnd(8) < 25:   
                m.status = 0
            else:
                return False
        if m.flinch:
            return False
        if m.conf:
            m.conf -= 1
            if m.conf > 0 and rnd(8) < 128:
                self.self_hit(m)
                return False
        if m.attract and rnd(8) < 128:
            return False
        if m.status == PAR and rnd(8) < 63:
            return False
        return True

    def self_hit(self, m):
        A, Df = estat(m, 0), estat(m, 1)
        if A > 255 or Df > 255:
            A, Df = max(1, (A // 4) & 255), max(1, (Df // 4) & 255)
        d = min(997, ((2 * m.lvl // 5 + 2) * 40 * A // Df) // 50) + 2
        if d > 1:
            d = d * self.roll() // 255
        m.hp = max(0, m.hp - d)

    def act(self, m, o, mv, idx, mode):
        if mode == "normal" and mv is not None and mv.effect != "RAGE":
            m.rage, m.rage_n = False, 1
        if mv is None:                                    
            m.recharge = False
            return
        if m.recharge:
            m.recharge = False
        if not self.can_move(m, o, mv, idx):
            m.charge, m.invuln = None, None
            m.rampage_left = m.rollout_left = m.rollout_n = m.bide_left = 0
            return
        if mode == "normal" and idx >= 0:
            if idx == m.dis_idx:
                return                                     
            m.pp[idx] -= 1
        if mode == "normal":
            if mv.effect not in ("PROTECT", "ENDURE", "DETECT"):
                m.protect_n = 0
            if mv.effect != "RAGE":
                m.rage = False
            if mv.effect != "FURY_CUTTER":
                m.fury_n = 0
            if mv.effect not in ("ROLLOUT",):
                m.rollout_left = m.rollout_n = 0
        m.dbond = m.dbond and mv.effect == "DESTINY_BOND"
        m.used[mv.name] = m.used.get(mv.name, 0) + 1
        m.last_mv = mv
        if mode == "charge2":
            m.charge, m.invuln = None, None
        if self.log is not None:
            self.L(f"T{self.turn} [{'a' if m is self.a else 'b'}] {m.name} uses {mv.name} (hp {m.hp}/{m.maxhp}) vs {o.name} (hp {o.hp}/{o.maxhp})")
        if mode == "bide":
            m.bide_left -= 1
            if m.bide_left == 0:
                dmg, m.bide_acc = m.bide_acc * 2, 0
                if dmg > 0:
                    self.deal(m, o, dmg, mv, True)
            return
        if mv.kind == "dmg":
            self.dmg_move(m, o, mv, mode)
            if mode == "rampage":
                m.rampage_left -= 1
                if m.rampage_left <= 0:
                    m.rampage_left = 0
                    self.confuse(m)
        else:
            self.status_move(m, o, mv, idx)
        if mv.name in ("FLAME_WHEEL", "SACRED_FIRE") and m.status == FRZ:
            m.status = 0

    def between_turns(self, order):
        rnd = self.rnd
        for m in order:                                    
            if m.future_left > 0:
                m.future_left -= 1
                if m.future_left == 0 and m.future_by is not None:
                    d = m.future_dmg
                    acc = acc_thresh(m.future_by, m, MV["FUTURE_SIGHT"])
                    if acc >= 255 or self.rnd(8) < acc:
                        m.hp = max(0, m.hp - max(1, d * self.roll() // 255 if d > 1 else d))
        if self.over():
            return True
        if self.weather == "sand":
            for m in order:
                if not ({"ROCK", "GROUND", "STEEL"} & set(m.types)):
                    m.hp = max(0, m.hp - max(1, m.maxhp // 8))
        if self.weather:
            self.weather_left -= 1
            if self.weather_left <= 0:
                self.weather = None
        if self.over():
            return True
        for m in order:
            o = self.other(m)
            if m.trap_left > 0:
                m.hp = max(0, m.hp - max(1, m.maxhp // 16))
                m.trap_left -= 1
                m.trapped = m.trap_left > 0
            if m.status == BRN or m.status == PSN:
                if m.status == PSN and m.toxic:
                    m.hp = max(0, m.hp - max(1, m.maxhp * m.toxic // 16))
                    m.toxic = min(15, m.toxic + 1)
                else:
                    m.hp = max(0, m.hp - max(1, m.maxhp // 8))
            if m.seeded and m.hp > 0:
                d = max(1, m.maxhp // 8)
                m.hp = max(0, m.hp - d)
                if o.hp > 0:
                    o.hp = min(o.maxhp, o.hp + d)
            if m.nightmare and m.status == SLP:
                m.hp = max(0, m.hp - max(1, m.maxhp // 4))
            if m.cursed:
                m.hp = max(0, m.hp - max(1, m.maxhp // 4))
            if self.over():
                return True
        for m in order:
            if m.perish > 0:
                m.perish -= 1
                if m.perish == 0:
                    m.hp = 0
        if self.over():
            return True
        for m in order:
            for f in ("reflect", "lscreen", "safeguard"):
                v = getattr(m, f)
                if v > 0:
                    setattr(m, f, v - 1)
            if m.encore_left > 0:
                m.encore_left -= 1
            if m.dis_left > 0:
                m.dis_left -= 1
                if m.dis_left == 0:
                    m.dis_idx = -1
            m.protecting = m.enduring = False
        return False
