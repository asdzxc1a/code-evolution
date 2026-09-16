"""SIENNA -- original, fully clothed adult stylized character for Blender 4.5.
Run: blender -b --factory-startup --python sienna.py -- --out output
Creates a new scene; never deletes existing scenes or changes preferences.
Static character sculpt: separate editable meshes, materials, curves, and cameras.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

P = math.pi
SCENE = None
COL = None
CHAR = []
HEAD = []

def mat(name, color, roughness=.4, metallic=0.0, skin=False):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    b=m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value=(*color,1)
    b.inputs['Roughness'].default_value=roughness; b.inputs['Metallic'].default_value=metallic
    if skin:
        b.inputs['Subsurface Weight'].default_value=.075
        b.inputs['Subsurface Radius'].default_value=(1,.45,.25)
    return m

def move(obj, name, material=None, head=False):
    obj.name=name
    for c in list(obj.users_collection): c.objects.unlink(obj)
    COL.objects.link(obj)
    if material is not None: obj.data.materials.append(material)
    if obj.type=='MESH':
        for p in obj.data.polygons: p.use_smooth=True
    CHAR.append(obj)
    if head: HEAD.append(obj)
    return obj

def mesh(name, verts, faces, material, sub=0, head=False):
    d=bpy.data.meshes.new(name+' geometry'); d.from_pydata(verts,[],faces); d.update()
    o=bpy.data.objects.new(name,d); COL.objects.link(o)
    if material: d.materials.append(material)
    for p in d.polygons: p.use_smooth=True
    if sub:
        mod=o.modifiers.new('Smooth editable surface','SUBSURF'); mod.levels=sub; mod.render_levels=sub
    CHAR.append(o)
    if head: HEAD.append(o)
    return o

def uv(name, location, scale, material, head=False, rot=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=location)
    o=move(bpy.context.object,name,material,head); o.scale=scale
    if rot: o.rotation_euler=rot
    return o

def curve(name, coords, radius, material, head=False, radii=None):
    d=bpy.data.curves.new(name,'CURVE'); d.dimensions='3D'; d.resolution_u=16
    d.bevel_depth=radius; d.bevel_resolution=3; d.use_fill_caps=True
    s=d.splines.new('BEZIER'); s.bezier_points.add(len(coords)-1)
    for i,(p,co) in enumerate(zip(s.bezier_points,coords)):
        p.co=co; p.handle_left_type='AUTO'; p.handle_right_type='AUTO'
        if radii: p.radius=radii[i]
    o=bpy.data.objects.new(name,d); COL.objects.link(o); d.materials.append(material); CHAR.append(o)
    if head: HEAD.append(o)
    return o

def loft(name, rings, material, sides=48, sub=2, cap=True, head=False, z_offset=None):
    # Each ring: z, half width, half depth, x center, y center.
    verts=[]
    for k,(z,rx,ry,cx,cy) in enumerate(rings):
        for i in range(sides):
            a=2*P*i/sides
            zz=z+(z_offset(k,a) if z_offset else 0)
            verts.append((cx+rx*math.cos(a),cy+ry*math.sin(a),zz))
    faces=[]
    for k in range(len(rings)-1):
        for i in range(sides):
            a=k*sides+i; b=k*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
    if cap:
        faces.extend([tuple(reversed(range(sides))),tuple((len(rings)-1)*sides+i for i in range(sides))])
    return mesh(name,verts,faces,material,sub,head)

def tube(name, rings, material, sides=20, sub=2, head=False):
    # Each ring: 3D center, lateral radius, second radius.
    verts=[]
    for j,(center,r1,r2) in enumerate(rings):
        c=Vector(center)
        t=Vector(rings[min(j+1,len(rings)-1)][0])-Vector(rings[max(0,j-1)][0]); t.normalize()
        ref=Vector((0,1,0))
        if abs(t.dot(ref))>.95: ref=Vector((0,0,1))
        u=ref.cross(t).normalized(); v=t.cross(u).normalized()
        for i in range(sides):
            a=2*P*i/sides; verts.append(c+r1*math.cos(a)*u+r2*math.sin(a)*v)
    faces=[]
    for j in range(len(rings)-1):
        for i in range(sides):
            a=j*sides+i; b=j*sides+(i+1)%sides; faces.append((a,b,b+sides,a+sides))
    faces.extend([tuple(reversed(range(sides))),tuple((len(rings)-1)*sides+i for i in range(sides))])
    return mesh(name,verts,faces,material,sub,head)

HEAD_RINGS=[(6.45,.04,.06,0,-.035),(6.49,.15,.16,0,-.035),(6.56,.26,.22,0,-.03),(6.67,.37,.27,0,-.01),(6.83,.46,.32,0,0),(7.02,.525,.38,0,.025),(7.20,.53,.405,0,.035),(7.40,.49,.39,0,.035),(7.57,.37,.30,0,.035),(7.68,.20,.17,0,.035),(7.72,.025,.025,0,.035)]

def face_y(x,z):
    for a,b in zip(HEAD_RINGS,HEAD_RINGS[1:]):
        if a[0]<=z<=b[0]:
            t=(z-a[0])/(b[0]-a[0]); rx=a[1]*(1-t)+b[1]*t; ry=a[2]*(1-t)+b[2]*t; cy=a[4]*(1-t)+b[4]*t
            return cy-ry*math.sqrt(max(.04,1-(x/rx)**2))
    return -.30

def make_eyes(skin,liner,white,iris,pupil,lip):
    for sign,label in [(-1,'L'),(1,'R')]:
        cx=sign*.245; cz=7.135
        verts=[]; faces=[]; nu=24; nv=10
        def edge(u,top):
            return cz+sign*u*.018+( .073 if top else -.052)*max(0,1-u*u)**.67
        for j in range(nv+1):
            t=j/nv
            for i in range(nu+1):
                u=-1+2*i/nu; x=cx+.159*u; z=edge(u,False)*(1-t)+edge(u,True)*t
                y=face_y(x,z)-.018-.027*(1-u*u)*math.sin(P*t)
                verts.append((x,y,z))
        for j in range(nv):
            for i in range(nu):
                a=j*(nu+1)+i; faces.append((a,a+1,a+nu+2,a+nu+1))
        mesh('Eye white '+label,verts,faces,white,1,True)
        yy=face_y(cx,cz)-.057
        uv('Iris rim '+label,(cx,yy,cz),(.065,.018,.065),pupil,True)
        uv('Hazel iris '+label,(cx,yy-.014,cz),(.050,.014,.052),iris,True)
        uv('Pupil '+label,(cx,yy-.025,cz),(.026,.009,.034),pupil,True)
        uv('Eye catchlight '+label,(cx-.017,yy-.035,cz+.023),(.012,.008,.012),white,True)
        uv('Eye glint '+label,(cx+.018,yy-.034,cz-.018),(.005,.005,.005),white,True)
        for top in [False,True]:
            pts=[]
            for i in range(13):
                u=-1+2*i/12; x=cx+.16*u; z=edge(u,top)
                pts.append((x,face_y(x,z)-.024,z))
            curve(('Upper eyeliner ' if top else 'Lower eyelid ')+label,pts,.012 if top else .012,liner if top else skin,True,[.25]+[1]*11+[.25])
        outer=cx+sign*.15
        curve('Eyeliner flick '+label,[(outer,face_y(outer,cz)-.031,cz+.016),(outer+sign*.060,face_y(outer+sign*.055,cz)-.025,cz+.048)],.011,liner,True,[1,.06])
        bx=[.105,.185,.29,.37,.405]
        bz=[7.325,7.355,7.37,7.344,7.319]
        curve('Sculpted brow '+label,[(sign*x,face_y(sign*x,z)-.031,z) for x,z in zip(bx,bz)],.027,liner,True,[.30,.9,1,.7,.07])
    # Lips with a cupid's bow and a small, closed smile.
    nu=32; nv=6
    for upper in [True,False]:
        verts=[]; faces=[]
        for j in range(nv+1):
            t=j/nv
            for i in range(nu+1):
                u=-1+2*i/nu; x=.172*u; center=6.766+.012*u*u
                delta=(.049*(1-u*u)-.020*math.exp(-(u/.20)**2)) if upper else -.049*(1-u*u)
                z=center+t*delta; y=face_y(x,z)-.013-.018*(1-u*u)*math.sin(P*t)-.010*(1-u*u)
                verts.append((x,y,z))
        for j in range(nv):
            for i in range(nu):
                a=j*(nu+1)+i; faces.append((a,a+1,a+nu+2,a+nu+1))
        mesh('Upper lip' if upper else 'Lower lip',verts,faces,lip,1,True)
    curve('Closed smile',[(x,face_y(x,6.766)-.026,6.766+.012*(x/.172)**2) for x in [-.172,-.12,-.06,0,.06,.12,.172]],.0045,liner,True,[.1,.7,1,1,1,.7,.1])

def build(out,quality):
    global SCENE,COL
    SCENE=bpy.data.scenes.new('SIENNA | Character Studio')
    if bpy.context.window: bpy.context.window.scene=SCENE
    COL=bpy.data.collections.new('01  SIENNA - editable character'); SCENE.collection.children.link(COL)
    skin=mat('Skin | warm porcelain',(.62,.335,.235),.43,skin=True)
    liner=mat('Brows and lashes | espresso',(.035,.012,.011),.48)
    lip=mat('Lipstick | muted rose',(.34,.036,.059),.32)
    hair=mat('Hair | dark chocolate',(.040,.012,.009),.31)
    hairlight=mat('Hair | satin ribbons',(.105,.035,.022),.34)
    burgundy=mat('Dress | oxblood satin',(.235,.010,.039),.29,.06)
    b=burgundy.node_tree.nodes.get('Principled BSDF'); b.inputs['Sheen Weight'].default_value=.28
    b.inputs['Coat Weight'].default_value=.12
    gold=mat('Jewelry | brushed champagne gold',(.72,.47,.19),.24,.80)
    black=mat('Shoes | black cherry patent',(.032,.007,.014),.20,.12)
    white=mat('Eyes | warm white',(.93,.91,.85),.22)
    iris=mat('Eyes | hazel',(.18,.23,.095),.27)
    pupil=mat('Eyes | dark iris rim',(.007,.010,.008),.26)
    # Mature proportions: long legs, small head relative to body, tailored silhouette.
    torso=[(3.53,.39,.26,.08,0),(3.70,.60,.35,.07,0),(3.99,.69,.365,.055,0),(4.20,.635,.34,.025,0),(4.48,.50,.276,0,0),(4.77,.43,.242,0,0),(5.04,.46,.265,0,0),(5.30,.54,.305,0,0),(5.52,.61,.36,0,-.015),(5.72,.64,.34,0,0),(5.93,.68,.265,0,.025),(6.04,.70,.225,0,.035),(6.12,.43,.195,0,.035),(6.18,.22,.172,0,.03)]
    loft('Body | torso',torso,skin)
    loft('Body | neck',[(6.01,.24,.185,0,.03),(6.14,.217,.175,0,.04),(6.34,.205,.175,0,.055),(6.54,.25,.205,0,.035),(6.61,.27,.20,0,.03)],skin)
    # Leg paths include a subtle contrapposto instead of a rigid T-pose.
    legs=[('R',[(.39,0,3.91),(.39,.005,3.67),(.37,.04,3.26),(.34,.02,2.68),(.36,-.05,2.24),(.37,.005,2.03),(.34,.10,1.70),(.34,.12,1.31),(.34,.12,.81),(.34,.11,.51)],[(.30,.29),(.32,.31),(.29,.28),(.215,.21),(.165,.17),(.174,.19),(.205,.22),(.17,.18),(.11,.115),(.09,.09)]),('L',[(-.36,0,3.90),(-.39,-.01,3.64),(-.40,-.02,3.24),(-.35,-.10,2.65),(-.33,-.17,2.25),(-.38,-.115,2.05),(-.47,-.015,1.76),(-.57,.03,1.29),(-.64,.025,.83),(-.67,.02,.51)],[(.30,.29),(.315,.305),(.28,.275),(.21,.205),(.164,.175),(.17,.19),(.20,.215),(.158,.175),(.107,.11),(.087,.09)])]
    for label,pts,rr in legs:
        tube('Body | leg '+label,[(p,*r) for p,r in zip(pts,rr)],skin,28,2)
        xx,yy,_=pts[-1]
        uv('Body | foot '+label,(xx,yy-.08,.35),(.135,.25,.18),skin,rot=(.50,0,0))
        tube('Pump | shoe '+label,[((xx,yy-.64,.13),.025,.035),((xx,yy-.52,.15),.13,.075),((xx,yy-.32,.18),.18,.115),((xx,yy-.14,.25),.15,.13),((xx,yy+.06,.39),.115,.12),((xx,yy+.18,.46),.12,.105),((xx,yy+.22,.45),.025,.035)],black,24,2)
        tube('Pump | stiletto '+label,[((xx,yy+.17,.43),.075,.067),((xx,yy+.17,.36),.068,.06),((xx,yy+.16,.085),.028,.03),((xx,yy+.16,.05),.030,.03)],black,20,1)
        curve('Pump | gold heel accent '+label,[(xx+.075,yy+.16,.41),(xx+.038,yy+.165,.22),(xx+.03,yy+.165,.09)],.008,gold)
        # Slim ankle strap with a small buckle.
        curve('Pump | ankle strap '+label,[(xx+.105*math.cos(a),yy+.098*math.sin(a),.60) for a in [i*2*P/24 for i in range(25)]],.023,black)
        uv('Pump | buckle '+label,(xx+.109,yy-.025,.602),(.019,.037,.038),gold)
    # Arms. Right hand rests on the hip; left arm hangs naturally.
    armR=[((.62,.02,6.02),.205,.205),((.79,.025,5.90),.218,.205),((.99,.03,5.62),.167,.17),((1.18,.02,5.25),.13,.14),((1.15,-.04,5.18),.125,.125),((1.06,-.13,5.12),.132,.128),((.88,-.22,4.98),.083,.082),((.82,-.245,4.94),.075,.073)]
    armL=[((-.62,.02,6.02),.205,.205),((-.78,.02,5.90),.211,.20),((-.88,.015,5.63),.17,.169),((-.97,-.005,5.24),.13,.135),((-.97,-.018,5.12),.14,.14),((-.995,-.055,4.88),.13,.127),((-1.025,-.11,4.55),.083,.082),((-1.02,-.13,4.48),.078,.073)]
    tube('Body | arm R',armR,skin,24,2); tube('Body | arm L',armL,skin,24,2)
    for label,x,y,z in [('L',-1.02,-.14,4.34),('R',.775,-.26,4.82)]:
        tilt=-.15 if label=='R' else .03
        uv('Hand | palm '+label,(x,y,z),(.119,.065,.18),skin,rot=(0,tilt,0))
        for i in range(4):
            dx=(i-1.5)*.05; length=[.19,.245,.225,.173][i]
            start=(x+dx,y-.01,z-.115)
            end=(x+dx+(.02 if label=='L' else -.04),y-.015,z-.115-length)
            middle=((start[0]+end[0])/2,y-.034,(start[2]+end[2])/2)
            tube('Hand | finger %s %s'%(label,i+1),[(start,.030,.029),(middle,.027,.027),(end,.018,.018),((end[0],end[1],end[2]-.018),.005,.005)],skin,12,2)
            uv('Manicure | %s %s'%(label,i+1),(end[0],end[1]-.018,end[2]+.034),(.018,.008,.035),lip)
        direction=1 if label=='L' else -1
        tube('Hand | thumb '+label,[((x+direction*.09,y,z+.015),.047,.04),((x+direction*.158,y-.015,z-.07),.035,.03),((x+direction*.155,y-.05,z-.14),.023,.022),((x+direction*.145,y-.05,z-.17),.008,.008)],skin,14,2)
    # Opaque, fitted dress, with separate editable straps and edge piping.
    dressrings=[(3.18,.62,.35,.075,0),(3.23,.628,.353,.075,0),(3.47,.666,.373,.07,0),(3.76,.72,.39,.064,0),(4.02,.728,.388,.05,0),(4.22,.668,.36,.025,0),(4.50,.534,.302,0,0),(4.79,.463,.27,0,0),(5.03,.493,.293,0,-.002),(5.32,.584,.35,0,-.013),(5.54,.65,.398,0,-.012),(5.70,.675,.383,0,-.004),(5.745,.669,.37,0,.0)]
    def dress_offset(k,a):
        if k<2: return .115*math.cos(a)
        if k>=len(dressrings)-2: return .075*math.cos(2*a)
        return 0
    dress=loft('Dress | fitted satin',dressrings,burgundy,64,2,False,z_offset=dress_offset)
    solid=dress.modifiers.new('Real fabric thickness','SOLIDIFY'); solid.thickness=.025
    for sign,label in [(-1,'L'),(1,'R')]:
        coords=[(sign*.47,-.267,5.76),(sign*.535,-.225,5.91),(sign*.605,-.075,6.067),(sign*.61,.085,6.075),(sign*.53,.23,5.92),(sign*.47,.27,5.77)]
        curve('Dress | shoulder strap '+label,coords,.050,burgundy)
    for k,label in [(0,'hem'),(len(dressrings)-1,'neckline')]:
        z,rx,ry,cx,cy=dressrings[k]
        curve('Dress | '+label+' piping',[(cx+rx*math.cos(a),cy+ry*math.sin(a),z+dress_offset(k,a)) for a in [2*P*i/64 for i in range(65)]],.010,gold)
    curve('Dress | waist detail',[(.468*math.cos(a),.276*math.sin(a),4.78) for a in [2*P*i/64 for i in range(65)]],.018,gold)
    uv('Dress | waist clasp',(.28,-.23,4.78),(.055,.018,.054),gold)
    for sign in [-1,1]:
        curve('Dress | tailored seam '+str(sign),[(sign*.29,-.31,5.54),(sign*.25,-.265,5.13),(sign*.22,-.245,4.80),(sign*.29,-.286,4.39),(sign*.40,-.315,4.01),(sign*.385,-.32,3.50)],.008,burgundy)
    # Head and connected nose sculpt.
    head=loft('Face | head',HEAD_RINGS,skin,64,2,True,True)
    bridge=uv('Face | bridge',(0,-.352,7.055),(.052,.054,.155),skin,True)
    tip=uv('Face | nose',(0,-.411,6.955),(.076,.071,.058),skin,True)
    alae=[uv('Face | nose wing '+str(s),(s*.061,-.377,6.937),(.044,.045,.033),skin,True) for s in [-1,1]]
    # Voxel union the nose and face to eliminate intersecting primitive seams.
    bpy.ops.object.select_all(action='DESELECT')
    for o in [head,bridge,tip]+alae:
        o.select_set(True); bpy.context.view_layer.objects.active=o
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        for mod in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active=head; bpy.ops.object.join()
    rem=head.modifiers.new('Face union','REMESH'); rem.mode='VOXEL'; rem.voxel_size=.018; rem.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=rem.name)
    sm=head.modifiers.new('Sculpt polish','SMOOTH'); sm.factor=.75; sm.iterations=5; bpy.ops.object.modifier_apply(modifier=sm.name)
    sub=head.modifiers.new('Final face smooth','SUBSURF'); sub.levels=1; sub.render_levels=1
    # Remove joined object references from our export lists.
    CHAR[:]=[o for o in CHAR if o.name in bpy.data.objects] if False else list(COL.objects)
    HEAD[:]=[o for o in COL.objects if o.name.startswith('Face |')]
    make_eyes(skin,liner,white,iris,pupil,lip)
    for sign,label in [(-1,'L'),(1,'R')]:
        uv('Ear | '+label,(sign*.503,.015,6.982),(.091,.067,.16),skin,True)
        earinner=mat('Ear blush '+label,(.43,.17,.12),.49,skin=True)
        uv('Ear | inner '+label,(sign*.539,-.039,6.987),(.037,.018,.090),earinner,True)
        curve('Earring | hoop '+label,[(sign*.56+.082*math.cos(a),-.017,6.767+.131*math.sin(a)) for a in [i*2*P/36 for i in range(37)]],.019,gold,True)
    # Hair cap follows the skull; the hairline stays above the eyebrows.
    verts=[]; faces=[]; nt=64; np=18
    for j in range(np+1):
        for i in range(nt):
            a=2*P*i/nt; front=max(0,-math.sin(a)); back=max(0,math.sin(a))
            phi_end=1.80-.57*front+.41*back
            phi=.015+(phi_end-.015)*j/np
            verts.append((.558*math.sin(phi)*math.cos(a),.055+.456*math.sin(phi)*math.sin(a),7.16+.625*math.cos(phi)))
    for j in range(np):
        for i in range(nt):
            a=j*nt+i; b=j*nt+(i+1)%nt; faces.append((a,b,b+nt,a+nt))
    mesh('Hair | swept cap',verts,faces,hair,2,True)
    # Scalp ridges suggest brushed hair without expensive hair simulation.
    for i in range(21):
        a=-P+.10+i*(P-.20)/20
        front=max(0,-math.sin(a)); phiend=1.80-.57*front
        pts=[]
        for k in range(7):
            t=k/6; phi=phiend*(1-t)+.20*t; aa=a+.30*t
            pts.append((.562*math.sin(phi)*math.cos(aa),.055+.460*math.sin(phi)*math.sin(aa),7.16+.632*math.cos(phi)))
        curve('Hair | brushed ridge %02d'%i,pts,.009,hairlight,True,[.2,.8,1,1,.9,.6,.05])
    # A side sweep above the forehead, not over the eye.
    curve('Hair | side sweep',[(-.40,-.26,7.52),(-.23,-.34,7.63),(.02,-.32,7.69),(.32,-.22,7.63),(.49,-.04,7.38)],.083,hair,True,[.1,.8,1,1,.10])
    tube('Hair | ponytail',[((0,.37,7.62),.17,.15),((.10,.66,7.60),.22,.19),((.28,.77,7.40),.27,.22),((.47,.73,7.10),.28,.235),((.64,.68,6.77),.26,.21),((.69,.66,6.42),.21,.18),((.62,.59,6.14),.15,.13),((.47,.51,5.98),.018,.018)],hair,28,2,True)
    curve('Hair | gold tie',[(.16*math.cos(a),.44+.07*math.sin(a),7.60+.15*math.sin(a)) for a in [i*2*P/24 for i in range(25)]],.03,gold,True)
    for i in range(7):
        dx=(i-3)*.044
        curve('Hair | ponytail ribbon %02d'%i,[(dx,.45,7.69),(.1+dx,.51,7.52),(.30+dx,.55,7.25),(.47+dx,.53,6.96),(.61+dx,.49,6.58),(.57+dx*.6,.45,6.24),(.47,.46,6.04)],.012,hairlight,True,[.1,.6,1,1,1,.7,.04])
    # A delicate necklace and bracelet complete the fashion look.
    curve('Jewelry | necklace',[(-.205,-.03,6.30),(-.18,-.16,6.27),(0,-.22,6.12),(.18,-.16,6.27),(.205,-.03,6.30)],.010,gold)
    uv('Jewelry | pendant',(0,-.226,6.105),(.035,.015,.051),gold)
    curve('Jewelry | bracelet',[(-1.02+.089*math.cos(a),-.10+.087*math.sin(a),4.57) for a in [2*P*i/32 for i in range(33)]],.018,gold)
    # Group controls are intentionally simple and non-destructive, not a fake rig.
    root=bpy.data.objects.new('SIENNA | move entire character',None); COL.objects.link(root)
    root.empty_display_type='CIRCLE'; root.empty_display_size=1.25
    for obj in list(COL.objects):
        if obj!=root: obj.parent=root
    head_control=bpy.data.objects.new('SIENNA | head tilt control',None); COL.objects.link(head_control)
    head_control.location=(0,0,6.45); head_control.parent=root; head_control.empty_display_size=.30
    bpy.context.view_layer.update()
    for obj in HEAD:
        world=obj.matrix_world.copy(); obj.parent=head_control; obj.matrix_world=world
    head_control.rotation_euler=(0,-.035,-.025)
    root['description']='Original adult character, fully clothed, static stylized sculpt'
    root['workflow']='Separate editable surfaces. Head tilt control; no skeleton or facial rig.'
    # Studio, camera, lights: not included in character-only glTF export.
    charcollection=COL
    COL=bpy.data.collections.new('02  Studio and cameras'); SCENE.collection.children.link(COL)
    stone=mat('Studio | warm alabaster',(.36,.27,.235),.50)
    floor=mat('Studio | dusty mauve',(.23,.155,.16),.64)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=1.55,depth=.14,location=(0,0,-.025))
    podium=move(bpy.context.object,'Studio | plinth',stone)
    mod=podium.modifiers.new('Soft plinth rim','BEVEL'); mod.width=.075; mod.segments=4
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.108)); move(bpy.context.object,'Studio | seamless floor',floor)
    def camera(name,location,target,scale):
        d=bpy.data.cameras.new(name); o=bpy.data.objects.new(name,d); COL.objects.link(o); o.location=location
        o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler(); d.type='ORTHO'; d.ortho_scale=scale; d.lens=70
        return o
    hero=camera('Camera | full character',(8,-20,10.0),(0,0,3.94),9.35)
    portrait=camera('Camera | portrait',(4.5,-15,8.6),(0,-.04,6.72),3.08)
    front=camera('Camera | front',(0,-22,7.8),(0,0,3.94),9.15)
    for name,loc,power,size,color in [('Key',(-6,-8,12),1500,7,(1,.82,.72)),('Fill',(6,-5,8),1050,6,(.80,.88,1)),('Rim',(4,5,11),1800,5,(1,.75,.58))]:
        d=bpy.data.lights.new(name,'AREA'); d.energy=power; d.shape='DISK'; d.size=size; d.color=color
        o=bpy.data.objects.new('Light | '+name,d); COL.objects.link(o); o.location=loc
        o.rotation_euler=(Vector((0,0,4.3))-o.location).to_track_quat('-Z','Y').to_euler()
    world=bpy.data.worlds.new('Studio | ambient'); world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.26,.27,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.35; SCENE.world=world
    SCENE.render.engine='CYCLES'; SCENE.cycles.device='CPU'; SCENE.cycles.samples=48 if quality=='final' else 16
    SCENE.cycles.use_denoising=True; SCENE.cycles.max_bounces=6
    SCENE.render.image_settings.file_format='PNG'; SCENE.render.film_transparent=False
    SCENE.view_settings.view_transform='AgX'; SCENE.view_settings.look='AgX - Medium High Contrast'
    SCENE.camera=hero; SCENE.render.resolution_x=900 if quality=='final' else 600; SCENE.render.resolution_y=1200 if quality=='final' else 800; SCENE.render.resolution_percentage=100
    # Convenient initial viewport.
    bpy.ops.object.select_all(action='DESELECT'); dress.select_set(True); bpy.context.view_layer.objects.active=dress
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.shading.type='MATERIAL' if False else 'SOLID'
                area.spaces.active.shading.color_type='MATERIAL'
    readme=bpy.data.texts.new('READ ME | SIENNA')
    readme.write('SIENNA / Original adult fashion character\n\nFully clothed stylized character. Burgundy satin dress, heels, dark ponytail.\n\nCollection 01 contains editable character surfaces, jewelry and hair curves.\nMove the character using SIENNA | move entire character.\nUse SIENNA | head tilt control for small head rotations.\nThis is a static concept sculpt, not animation-ready production topology.\nNo skeletal rig, facial rig, UV atlas, or baked textures are claimed.\nCollection 02 contains the studio and three cameras.\nMaterials are editable in Material Properties.\n')
    # Export only character geometry; convert a duplicate scene's curves for glTF.
    blend=out/'Sienna_Character.blend'; SCENE.render.filepath=str(out/'Sienna_Full.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.render.render(write_still=True,scene=SCENE.name)
    SCENE.camera=portrait; SCENE.render.resolution_x=1000 if quality=='final' else 640; SCENE.render.resolution_y=1000 if quality=='final' else 640
    SCENE.render.filepath=str(out/'Sienna_Portrait.png'); bpy.ops.render.render(write_still=True,scene=SCENE.name)
    SCENE.camera=hero; SCENE.render.resolution_x=900 if quality=='final' else 600; SCENE.render.resolution_y=1200 if quality=='final' else 800
    SCENE.render.filepath='//Sienna_Full.png'; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    # Save was completed before making the temporary export-only duplicates.
    bpy.ops.object.select_all(action='DESELECT')
    duplicates=[]
    bpy.context.view_layer.update()
    for source in list(charcollection.objects):
        if source.type not in {'MESH','CURVE'}: continue
        dup=source.copy(); dup.data=source.data.copy(); SCENE.collection.objects.link(dup)
        dup.matrix_world=source.matrix_world.copy(); world=dup.matrix_world.copy(); dup.parent=None; dup.matrix_world=world
        duplicates.append(dup); dup.select_set(True)
    if duplicates:
        bpy.context.view_layer.objects.active=duplicates[0]; bpy.ops.object.convert(target='MESH')
        bpy.ops.export_scene.gltf(filepath=str(out/'Sienna_Character.glb'),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_cameras=False,export_lights=False)
    meshes=[o for o in charcollection.objects if o.type=='MESH']
    proof={'status':'PASS','blender':bpy.app.version_string,'character':'Sienna','style':'adult, clothed, stylized fashion character','editable_mesh_objects':len(meshes),'editable_curve_objects':sum(o.type=='CURVE' for o in charcollection.objects),'material_count':len(bpy.data.materials),'rig':'static sculpt with root and head controls; no skeleton','files':{}}
    for path in out.iterdir():
        if path.suffix in {'.blend','.png','.glb'}: proof['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    assert (out/'Sienna_Character.glb').stat().st_size>10000
    (out/'proof.json').write_text(json.dumps(proof,indent=2))
    (out/'README.txt').write_text(readme.as_string())
    print('SIENNA_CHARACTER_SUCCESS'); print(json.dumps(proof,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',required=True); p.add_argument('--quality',choices=['preview','final'],default='final')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out=Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    build(out,args.quality)
