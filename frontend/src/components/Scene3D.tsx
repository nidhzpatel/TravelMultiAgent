import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Stars } from '@react-three/drei'
import * as THREE from 'three'

function Particles({ count = 300 }: { count?: number }) {
  const points = useRef<THREE.Points>(null)

  const [positions, velocities] = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const vel = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const radius = 2.2 + Math.random() * 0.8
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      pos[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = radius * Math.cos(phi)
      vel[i * 3] = (Math.random() - 0.5) * 0.001
      vel[i * 3 + 1] = (Math.random() - 0.5) * 0.001
      vel[i * 3 + 2] = (Math.random() - 0.5) * 0.001
    }
    return [pos, vel]
  }, [count])

  useFrame(() => {
    if (!points.current) return
    const pos = points.current.geometry.attributes.position.array as Float32Array
    for (let i = 0; i < count; i++) {
      pos[i * 3] += velocities[i * 3]
      pos[i * 3 + 1] += velocities[i * 3 + 1]
      pos[i * 3 + 2] += velocities[i * 3 + 2]
      const r = Math.sqrt(pos[i * 3] ** 2 + pos[i * 3 + 1] ** 2 + pos[i * 3 + 2] ** 2)
      if (r < 2.1 || r > 3.2) {
        velocities[i * 3] *= -1
        velocities[i * 3 + 1] *= -1
        velocities[i * 3 + 2] *= -1
      }
    }
    points.current.geometry.attributes.position.needsUpdate = true
    points.current.rotation.y += 0.0005
  })

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.025}
        color="#67e8f9"
        transparent
        opacity={0.8}
        sizeAttenuation
      />
    </points>
  )
}

function OrbitRings() {
  const group = useRef<THREE.Group>(null)
  useFrame(() => {
    if (group.current) {
      group.current.rotation.x += 0.0008
      group.current.rotation.y += 0.0012
    }
  })

  return (
    <group ref={group}>
      {[2.6, 3.0, 3.4].map((radius, idx) => (
        <mesh key={idx} rotation={[Math.PI / 2.5, 0, 0]}>
          <torusGeometry args={[radius, 0.004, 8, 128]} />
          <meshBasicMaterial
            color={idx === 1 ? '#8b5cf6' : '#06b6d4'}
            transparent
            opacity={0.25}
          />
        </mesh>
      ))}
    </group>
  )
}

function Earth() {
  const mesh = useRef<THREE.Mesh>(null)
  useFrame(() => {
    if (mesh.current) {
      mesh.current.rotation.y += 0.0015
    }
  })

  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[1.6, 64, 64]} />
      <meshStandardMaterial
        color="#1e3a8a"
        emissive="#0c4a6e"
        emissiveIntensity={0.4}
        roughness={0.7}
        metalness={0.2}
      />
    </mesh>
  )
}

function Atmosphere() {
  return (
    <mesh scale={[1.08, 1.08, 1.08]}>
      <sphereGeometry args={[1.6, 64, 64]} />
      <meshBasicMaterial
        color="#06b6d4"
        transparent
        opacity={0.12}
        side={THREE.BackSide}
      />
    </mesh>
  )
}

function CameraController() {
  const targetX = useRef(0)
  const targetY = useRef(0)
  const currentX = useRef(0)
  const currentY = useRef(0)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      targetX.current = (e.clientX / window.innerWidth - 0.5) * 1.2
      targetY.current = (e.clientY / window.innerHeight - 0.5) * -0.8
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  useFrame(() => {
    currentX.current += (targetX.current - currentX.current) * 0.04
    currentY.current += (targetY.current - currentY.current) * 0.04
    // Framer Motion spring imported but not used here to avoid R3F hook conflict;
    // manual lerp gives smooth, interruptible parallax.
  })

  useFrame((state) => {
    state.camera.position.x = currentX.current
    state.camera.position.y = currentY.current
    state.camera.lookAt(0, 0, 0)
  })

  return null
}

function SceneContents() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={1.2} color="#f8fafc" />
      <pointLight position={[-10, -5, -10]} intensity={0.8} color="#8b5cf6" />
      <Earth />
      <Atmosphere />
      <OrbitRings />
      <Particles count={350} />
      <Stars radius={80} depth={50} count={2500} factor={4} saturation={0.8} fade speed={0.5} />
      <CameraController />
    </>
  )
}

interface Scene3DProps {
  className?: string
}

export default function Scene3D({ className = '' }: Scene3DProps) {
  return (
    <div className={`absolute inset-0 ${className}`}>
      <Canvas
        camera={{ position: [0, 0, 6.5], fov: 45 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <SceneContents />
      </Canvas>
    </div>
  )
}
