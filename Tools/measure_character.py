"""
Measure the proportions of a rigged humanoid character (VRM / glTF / FBX).

The atelier's shape tables (Tools/dai/anime/atelier: body.TORSO_* / ARM / LEG, head.LOWER, paint.EYE and the
warp in build.py) were fitted to numbers taken with this script from reference anime figures. Only
measurements are used - joint heights, cross-section sizes, where the eyes and mouth sit - never the
reference's geometry or textures, and the reference files are not part of the repository.

    python Tools/measure_character.py out.json model_a.vrm [model_b.fbx ...]

Per model the JSON holds joint positions, head height / chin / crown, the head's half width, front and
back depth by height, the iris / lash / brow / mouth boxes (VRoid-style material names), torso sections,
arm and leg radii and the hand size. Units: metres, rest pose, the character facing -Y.
"""

import sys, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import bpy, numpy as np
from dai import blend
from dai.anime import models as M
out = {}
for path in sys.argv[2:]:
    blend.reset_scene()
    arm, meshes = M.load(path, log=lambda *a: None)
    B = {b.name: np.array(arm.matrix_world @ b.head_local) for b in arm.data.bones}
    V, mat = [], []
    for m in meshes:
        co = np.array([m.matrix_world @ v.co for v in m.data.vertices])
        names = [s.material.name.lower() if s.material else "" for s in m.material_slots]
        vm = np.full(len(co), "", dtype=object)
        for p in m.data.polygons:
            for vi in p.vertices: vm[vi] = names[p.material_index]
        V.append(co); mat += list(vm)
    V = np.concatenate(V); mat = np.array(mat)
    skin = np.array([("skin" in n) for n in mat]); body = np.array([("body" in n and "skin" in n) for n in mat])
    face = np.array([("face" in n and "skin" in n) for n in mat])
    r = {}
    r["joints"] = {k: [round(float(x), 4) for x in B[k]] for k in ("pelvis","spine_01","spine_02","spine_03","neck_01","head","upperarm_l","lowerarm_l","hand_l","thigh_l","calf_l","foot_l","ball_l") if k in B}
    F = V[face]; crown = F[:,2].max(); chin = F[np.abs(F[:,0]) < 0.01][:,2].min(); hb = B["head"][2]
    r["head"] = dict(crown=round(float(crown),4), chin=round(float(chin),4), head_bone=round(float(hb),4), height=round(float(crown-chin),4))
    prof = []
    for t in np.linspace(0.0, 1.0, 21):          # 0 chin .. 1 crown
        z = chin + t * (crown - chin); sl = F[np.abs(F[:,2]-z) < 0.004]
        if len(sl) < 6: continue
        mid = sl[np.abs(sl[:,0]) < 0.006]
        prof.append([round(float(t),2), round(float(np.abs(sl[:,0]).max()),4), round(float(-(mid[:,1].min()) if len(mid) else float('nan')),4), round(float(sl[:,1].max()),4)])
    r["head_profile_t_halfw_front_back"] = prof
    for key, kw in (("iris", "eyeiris"), ("mouth", "facemouth"), ("brow", "facebrow"), ("lash", "eyeline")):
        sel = np.array([kw in n for n in mat]); P = V[sel & (V[:,0] > 0.002)] if key in ("iris","brow","lash") else V[sel]
        if len(P): r[key] = dict(lo=[round(float(x),4) for x in P.min(0)], hi=[round(float(x),4) for x in P.max(0)])
    Bd = V[body]
    tor = []
    for z in np.linspace(B["thigh_l"][2]-0.04, B["neck_01"][2], 14):
        sl = Bd[(np.abs(Bd[:,2]-z) < 0.006) & (np.abs(Bd[:,0]) < 0.19)]
        if len(sl) < 6: continue
        tor.append([round(float(z),3), round(float(np.abs(sl[:,0]).max()),4), round(float(-sl[:,1].min()),4), round(float(sl[:,1].max()),4)])
    r["torso_z_halfw_front_back"] = tor
    arm_r = []
    for x in np.linspace(B["upperarm_l"][0], B["hand_l"][0], 9):
        sl = Bd[(np.abs(Bd[:,0]-x) < 0.006)]
        if len(sl) > 5: arm_r.append([round(float(x),3), round(float((sl[:,2].max()-sl[:,2].min())/2),4), round(float((sl[:,1].max()-sl[:,1].min())/2),4), round(float((sl[:,2].max()+sl[:,2].min())/2),4)])
    r["arm_x_rz_ry_cz"] = arm_r
    leg = []
    for z in np.linspace(B["thigh_l"][2]-0.03, B["foot_l"][2]+0.01, 12):
        sl = Bd[(np.abs(Bd[:,2]-z) < 0.006) & (Bd[:,0] > 0.012)]
        if len(sl) > 5: leg.append([round(float(z),3), round(float((sl[:,0].max()-sl[:,0].min())/2),4), round(float((sl[:,1].max()-sl[:,1].min())/2),4), round(float((sl[:,0].max()+sl[:,0].min())/2),4), round(float((sl[:,1].max()+sl[:,1].min())/2),4)])
    r["leg_z_rx_ry_cx_cy"] = leg
    H = Bd[Bd[:,0] > B["hand_l"][0]]
    r["hand"] = dict(length=round(float(H[:,0].max()-B["hand_l"][0]),4), width=round(float(H[:,1].max()-H[:,1].min()),4)) if len(H) else {}
    out[path.split("/")[-1]] = r
json.dump(out, open(sys.argv[1], "w"), indent=0)
print("measured", list(out))
