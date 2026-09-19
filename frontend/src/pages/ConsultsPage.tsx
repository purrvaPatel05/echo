import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import type { ConsultMessage } from '@/api/client'
import { useConsults, useMe, useMessages } from '@/api/hooks'
import { socket } from '@/api/socket'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

function Thread({ consultId }: { consultId: string }) {
  const qc = useQueryClient()
  const { data: me } = useMe()
  const { data: messages } = useMessages(consultId)
  const [body, setBody] = useState('')
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onMessage = (msg: ConsultMessage) => {
      if (msg.consult_id !== consultId) return
      qc.setQueryData<ConsultMessage[]>(['messages', consultId], (old = []) =>
        old.some((m) => m.id === msg.id) ? old : [...old, msg],
      )
      qc.invalidateQueries({ queryKey: ['consults'] })
    }
    socket.emit('join', { consult_id: consultId })
    socket.on('message', onMessage)
    return () => {
      socket.emit('leave', { consult_id: consultId })
      socket.off('message', onMessage)
    }
  }, [consultId, qc])

  useEffect(() => bottom.current?.scrollIntoView({ behavior: 'smooth' }), [messages])

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-2 overflow-y-auto p-4">
        {messages?.length === 0 && <p className="text-sm text-muted-foreground">Send a message to start the consult.</p>}
        {messages?.map((m) => (
          <div key={m.id} className={cn('flex', m.sender_id === me?.id && 'justify-end')}>
            <div
              className={cn(
                'max-w-[75%] rounded-lg px-3 py-2 text-sm',
                m.sender_id === me?.id ? 'bg-primary text-primary-foreground' : 'bg-secondary',
              )}
            >
              {m.body}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <form
        className="flex gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (!body.trim()) return
          socket.emit('send_message', { consult_id: consultId, body })
          setBody('')
        }}
      >
        <Input placeholder="Message…" value={body} onChange={(e) => setBody(e.target.value)} />
        <Button type="submit">Send</Button>
      </form>
    </div>
  )
}

export default function ConsultsPage() {
  const { data: consults } = useConsults()
  const [selected, setSelected] = useState<string | null>(null)
  const active = consults?.find((c) => c.id === selected)

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Consults</h1>
      <div className="grid h-[32rem] grid-cols-[16rem_1fr] overflow-hidden rounded-lg border bg-card">
        <ul className="overflow-y-auto border-r">
          {consults?.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => setSelected(c.id)}
                className={cn('w-full px-4 py-3 text-left hover:bg-secondary', c.id === selected && 'bg-secondary')}
              >
                <div className="text-sm font-medium">{c.specialist.name}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {c.last_message?.body ?? c.specialist.specialty}
                </div>
              </button>
            </li>
          ))}
        </ul>
        {active ? (
          <Thread key={active.id} consultId={active.id} />
        ) : (
          <div className="grid place-items-center text-sm text-muted-foreground">Select a physician to ping</div>
        )}
      </div>
    </div>
  )
}
