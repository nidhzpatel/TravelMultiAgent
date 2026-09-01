import { useState } from 'react'
import type { TravelPlanRequest } from '../types'

interface RequestFormProps {
  onSubmit: (request: TravelPlanRequest) => void
  isLoading: boolean
}

const today = new Date().toISOString().split('T')[0]

export default function RequestForm({ onSubmit, isLoading }: RequestFormProps) {
  const [destination, setDestination] = useState('Tokyo')
  const [origin, setOrigin] = useState('Osaka')
  const [startDate, setStartDate] = useState(today)
  const [endDate, setEndDate] = useState(today)
  const [travelers, setTravelers] = useState(2)
  const [budget, setBudget] = useState(3000)
  const [interests, setInterests] = useState('temples, street food, tech')
  const [travelStyle, setTravelStyle] = useState('balanced')
  const [dietary, setDietary] = useState('')
  const [mobility, setMobility] = useState('')
  const [freeText, setFreeText] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      destination: destination.trim(),
      origin: origin.trim(),
      start_date: startDate,
      end_date: endDate,
      travelers,
      total_budget_usd: budget,
      currency: 'USD',
      total_budget: budget,
      exchange_rate: 1,
      interests: interests
        .split(',')
        .map((i) => i.trim())
        .filter(Boolean),
      travel_style: travelStyle,
      dietary_notes: dietary.trim() || undefined,
      mobility_notes: mobility.trim() || undefined,
      free_text: freeText.trim() || undefined,
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="destination">Destination *</label>
      <input
        id="destination"
        type="text"
        value={destination}
        onChange={(e) => setDestination(e.target.value)}
        required
      />

      <label htmlFor="origin">Origin (leave blank if already at destination)</label>
      <input
        id="origin"
        type="text"
        value={origin}
        onChange={(e) => setOrigin(e.target.value)}
      />

      <label htmlFor="startDate">Start date *</label>
      <input
        id="startDate"
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
        required
      />

      <label htmlFor="endDate">End date *</label>
      <input
        id="endDate"
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
        required
      />

      <label htmlFor="travelers">Travelers *</label>
      <input
        id="travelers"
        type="number"
        min={1}
        value={travelers}
        onChange={(e) => setTravelers(Number(e.target.value))}
        required
      />

      <label htmlFor="budget">Total budget (USD) *</label>
      <input
        id="budget"
        type="number"
        min={1}
        value={budget}
        onChange={(e) => setBudget(Number(e.target.value))}
        required
      />

      <label htmlFor="interests">Interests (comma-separated)</label>
      <input
        id="interests"
        type="text"
        value={interests}
        onChange={(e) => setInterests(e.target.value)}
      />

      <label htmlFor="style">Travel style</label>
      <select
        id="style"
        value={travelStyle}
        onChange={(e) => setTravelStyle(e.target.value)}
      >
        <option value="budget">Budget</option>
        <option value="balanced">Balanced</option>
        <option value="luxury">Luxury</option>
      </select>

      <label htmlFor="dietary">Dietary notes</label>
      <input
        id="dietary"
        type="text"
        value={dietary}
        onChange={(e) => setDietary(e.target.value)}
      />

      <label htmlFor="mobility">Mobility notes</label>
      <input
        id="mobility"
        type="text"
        value={mobility}
        onChange={(e) => setMobility(e.target.value)}
      />

      <label htmlFor="freeText">Additional notes</label>
      <textarea
        id="freeText"
        rows={3}
        value={freeText}
        onChange={(e) => setFreeText(e.target.value)}
      />

      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Planning...' : 'Plan Trip'}
      </button>
    </form>
  )
}
