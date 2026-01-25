// Example of how the Frontend should authenticate with the Supabase Backend

import { createClient } from '@supabase/supabase-js'

// 1. Initialize Supabase Client
const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY
const supabase = createClient(supabaseUrl, supabaseAnonKey)

async function callAgentAPI(userQuery) {
  // 2. Get the current session
  const { data: { session }, error } = await supabase.auth.getSession()

  if (error || !session) {
    console.error('User not logged in')
    return
  }

  // 3. Extract the Access Token (JWT)
  const token = session.access_token

  // 4. Call the Python Backend with the Token
  try {
    const response = await fetch('http://localhost:8001/v1/agent/calculate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}` // <--- Critical Step
      },
      body: JSON.stringify({
        query: userQuery
      })
    })

    if (!response.ok) {
      if (response.status === 401) {
        console.error('Unauthorized! Token invalid or expired.')
      }
      throw new Error(`API Error: ${response.statusText}`)
    }

    const data = await response.json()
    console.log('Agent Response:', data)
    return data

  } catch (err) {
    console.error(err)
  }
}
