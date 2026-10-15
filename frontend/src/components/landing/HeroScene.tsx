"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { SVGLoader } from "three/examples/jsm/loaders/SVGLoader.js";
import { cityRow, domePath, rowPath } from "@/components/scenery/geometry";

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

/** Hover-cars streaking across the sky lanes, each with a glowing tail light. */
function SkyTraffic() {
  const lanes = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => ({
        y: 1.4 + (i % 4) * 0.9,
        z: -8 - (i % 3) * 4,
        speed: (1.6 + (i % 5) * 0.7) * (i % 2 ? 1 : -1),
        offset: i * 7,
        color: i % 3 === 0 ? new THREE.Color(0.4, 2.2, 2.4) : new THREE.Color(2.4, 0.9, 0.3),
      })),
    [],
  );
  const refs = useRef<(THREE.Mesh | null)[]>([]);
  useFrame(({ clock }) => {
    lanes.forEach((l, i) => {
      const m = refs.current[i];
      if (m) m.position.x = ((((clock.elapsedTime * l.speed + l.offset) % 48) + 48) % 48) - 24;
    });
  });
  return (
    <group>
      {lanes.map((l, i) => (
        <mesh key={i} ref={(m) => void (refs.current[i] = m)} position={[0, l.y, l.z]}>
          <planeGeometry args={[0.55, 0.05]} />
          <meshBasicMaterial color={l.color} toneMapped={false} />
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
  const far = rowPath(cityRow(11, 1600, 120, 300, 180), 740);
  const mid = `${rowPath(cityRow(23, 1600, 90, 230, 240), 800)} ${domePath(420, 800, 90)} ${domePath(1190, 800, 120)}`;
  const near = rowPath(cityRow(5, 1600, 50, 150, 300), 870);
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
      <Layer d={`${far} M0,740 L1600,740 L1600,1100 L0,1100 Z`} z={-18} color="#100303" />
      <Layer d={`${mid} M0,800 L1600,800 L1600,1100 L0,1100 Z`} z={-10} color="#080202" />
      <Layer d={`${near} M0,860 Q400,850 800,868 T1600,858 L1600,1100 L0,1100 Z`} z={-4} color="#030000" />
      <SkyTraffic />
      <Embers />
      <EffectComposer>
        <Bloom intensity={1.4} luminanceThreshold={0.6} mipmapBlur />
      </EffectComposer>
    </Canvas>
  );
}
