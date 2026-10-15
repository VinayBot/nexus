"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { SVGLoader } from "three/examples/jsm/loaders/SVGLoader.js";
import { hallPath, pagodaPath, pine } from "@/components/scenery/geometry";

/** SVG path data (1600×900 space, y down) → flat silhouette meshes. */
function useSilhouette(d: string) {
  return useMemo(() => {
    const data = new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg"><path d="${d}"/></svg>`);
    const shapes = data.paths.flatMap((p) => SVGLoader.createShapes(p));
    const geo = new THREE.ShapeGeometry(shapes);
    geo.scale(0.02, -0.02, 1); // svg px → world units, flip y
    geo.translate(-16, 9, 0);
    return geo;
  }, [d]);
}

/** Scaled by distance so every layer spans the view; the y-flip reverses winding, hence DoubleSide. */
function Layer({ d, z, color, opacity = 1 }: { d: string; z: number; color: string; opacity?: number }) {
  const geo = useSilhouette(d);
  const s = (10 - z) * 0.06;
  return (
    <mesh geometry={geo} position={[0, 0.2, z]} scale={[s, s, 1]}>
      <meshBasicMaterial
        color={color}
        transparent={opacity < 1}
        opacity={opacity}
        side={THREE.DoubleSide}
        toneMapped={false}
      />
    </mesh>
  );
}

function Sun() {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (ref.current) ref.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 0.6) * 0.015);
  });
  return (
    <mesh ref={ref} position={[0, 0.4, -40]}>
      <circleGeometry args={[9, 96]} />
      <meshBasicMaterial color={new THREE.Color(2.4, 1.15, 0.35)} toneMapped={false} />
    </mesh>
  );
}

function Embers({ count = 140 }: { count?: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const a = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      a[i * 3] = (Math.random() - 0.5) * 34;
      a[i * 3 + 1] = (Math.random() - 0.5) * 18;
      a[i * 3 + 2] = -2 - Math.random() * 18;
    }
    return a;
  }, [count]);
  useFrame((_, dt) => {
    const geo = ref.current?.geometry;
    if (!geo) return;
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < count; i++) {
      let y = pos.getY(i) + dt * (0.4 + (i % 7) * 0.08);
      if (y > 9) y = -9;
      pos.setY(i, y);
      pos.setX(i, pos.getX(i) + Math.sin(y + i) * dt * 0.15);
    }
    pos.needsUpdate = true;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.09}
        color={new THREE.Color(2.2, 1.1, 0.4)}
        toneMapped={false}
        transparent
        opacity={0.9}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

function Birds() {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.position.x = ((clock.elapsedTime * 1.4) % 44) - 22;
    ref.current.position.y = 3.6 + Math.sin(clock.elapsedTime * 0.7) * 0.3;
  });
  const flock = [
    [0, 0],
    [-0.7, 0.3],
    [-1.4, 0.55],
    [0.7, 0.35],
    [1.3, 0.6],
  ];
  return (
    <group ref={ref} position={[0, 3.6, -12]}>
      {flock.map(([x, y], i) => (
        <mesh key={i} position={[x!, y!, 0]}>
          <planeGeometry args={[0.32, 0.05]} />
          <meshBasicMaterial color="#140909" />
        </mesh>
      ))}
    </group>
  );
}

/** Camera drifts toward the pointer: layers at different depths give parallax. */
function Parallax() {
  const { camera, pointer } = useThree();
  useFrame(() => {
    camera.position.x += (pointer.x * 1.6 - camera.position.x) * 0.04;
    camera.position.y += (pointer.y * 0.6 + 0.2 - camera.position.y) * 0.04;
    camera.lookAt(0, 0.4, -20);
  });
  return null;
}

export default function HeroScene() {
  const pines = [pine(120, 900, 330, 3), pine(260, 900, 220, 11), pine(1420, 900, 360, 7), pine(1530, 900, 240, 19)];
  const pinePath = pines
    .map((p) =>
      [
        p.trunk,
        ...p.pads.map(
          (e) => `M${e.cx - e.rx},${e.cy} a${e.rx},${e.ry} 0 1,0 ${e.rx * 2},0 a${e.rx},${e.ry} 0 1,0 ${-e.rx * 2},0`,
        ),
      ].join(" "),
    )
    .join(" ");
  return (
    <Canvas camera={{ position: [0, 0.2, 10], fov: 55 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }}>
      <Parallax />
      <Sun />
      <Layer
        d="M0,700 C180,640 300,610 430,650 C560,690 640,600 780,610 C930,620 1010,690 1160,660 C1300,630 1420,600 1600,650 L1600,1100 L0,1100 Z"
        z={-26}
        color="#160504"
        opacity={0.9}
      />
      <Layer
        d={`${hallPath(330, 760, 260)} ${hallPath(1240, 770, 300)} M0,760 L1600,770 L1600,1100 L0,1100 Z`}
        z={-14}
        color="#0b0303"
      />
      <Layer
        d={`${pagodaPath(1050, 840, 150, 5)} ${pagodaPath(560, 860, 110, 3)} ${hallPath(800, 880, 420)} M0,850 Q400,830 800,860 T1600,845 L1600,1100 L0,1100 Z`}
        z={-6}
        color="#050101"
      />
      <Layer d={pinePath} z={-3} color="#020000" />
      <Birds />
      <Embers />
      <EffectComposer>
        <Bloom intensity={1.4} luminanceThreshold={0.6} mipmapBlur />
      </EffectComposer>
    </Canvas>
  );
}
