import { useEffect, useState } from 'react';

interface VerticalResizeHandleProps {
  onDrag: (deltaY: number) => void;
}

export function VerticalResizeHandle({ onDrag }: VerticalResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      onDrag(e.movementY);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, onDrag]);

  return (
    <div
      className={`flex items-center justify-center gap-1.5 py-1 cursor-row-resize select-none group relative z-10 ${
        isDragging ? 'bg-slate-100' : ''
      }`}
      onMouseDown={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`w-1 h-1 rounded-full transition-all ${
            isDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
          }`}
        />
      ))}
    </div>
  );
}
