// api/chat.js — Vercel Serverless Function
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { messages } = req.body;
  if (!messages || !Array.isArray(messages)) {
    return res.status(400).json({ error: 'messages array is required' });
  }

  const SYSTEM_PROMPT = `તમે એક AI બસ બુકિંગ સહાયક છો. તમે ફક્ત ગુજરાતી ભાષામાં જ વાત કરો છો — ક્યારેય અંગ્રેજી વાપરશો નહીં.

    તમારું કામ:
    1. વપરાશકર્તા પાસેથી પ્રવાસ વિગતો મેળવો: ક્યાંથી → ક્યાં, તારીખ, સીટ સંખ્યા
    2. ઉપલબ્ધ બસ વિકલ્પો સૂચવો (ઉદા: AC સ્લીપર ₹450, સામાન્ય ₹280)
    3. પ્રવાસી નામ અને ફોન નંબર લો
    4. બુકિંગ કન્ફર્મ કરો અને PNR નંબર આપો

    નિયમો:
    - ફક્ત ગુજરાતીમાં જ જવાબ આપો
    - ટૂંકા, સ્પષ્ટ સવાલો પૂછો
    - મૈત્રીભર્યો, સ્નેહાળ સ્વભાવ રાખો
    - ઇમોજી વાપરો 🚌 🎉 ✅
    - PNR ફોર્મેટ: GJ + 6 digit number (ઉદા: GJ123456)`;

  try {
    const url = "https://agents-playground.livekit.io/#?liveKitUrl=wss://busbooking-p52t2etx.livekit.cloud&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoiVXNlciIsInZpZGVvIjp7InJvb21Kb2luIjp0cnVlLCJyb29tIjoiYnVzLWJvb2tpbmctcm9vbSIsImNhblB1Ymxpc2giOnRydWUsImNhblN1YnNjcmliZSI6dHJ1ZSwiY2FuUHVibGlzaERhdGEiOnRydWV9LCJzdWIiOiJ1c2VyLTEyMyIsImlzcyI6IkFQSTlnYlN2TnBRamlMbSIsIm5iZiI6MTc3MzczNzQyMywiZXhwIjoxNzczNzU5MDIzfQ.9RHr9PvTsxtytd7eB9SbtRioyHgEHYDMnDrJ-w6JwlI&autoconnect=true"
    const anthropicRes = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        system: SYSTEM_PROMPT,
        messages
      })
    });

    if (!anthropicRes.ok) {
      const err = await anthropicRes.json();
      console.error('Anthropic API error:', err);
      return res.status(anthropicRes.status).json({ error: err });
    }

    const data = await anthropicRes.json();
    return res.status(200).json(data);

  } catch (error) {
    console.error('Server error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
