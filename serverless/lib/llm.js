import { fetch } from 'sdk';

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || 'DUMMY_API_KEY_FOR_TESTING';
const LLM_GEMINI_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;
const LLM_OLLAMA_ENDPOINT = 'http://localhost:11434/api/generate';

const SYSTEM_PROMPT_GEN_EXAMPLE = `
You are a multilingual language model specialized in generating clear and natural example sentences.
Given a single word (in English or Japanese, NOT Chinese), generate a simple and appropriate example sentence that uses the word naturally.
Requirements:

    Detect the input language (English or Japanese) automatically.

    Write the example sentence in the same language as the input word.

    Ensure the sentence is correct, natural, and understandable by beginner to intermediate learners.

    If the word has multiple meanings, choose the most common or basic meaning unless specified otherwise.

    Output only the example sentence, no explanations or extra text.

Examples:

    Input: write an example for "happy" Output: "She felt happy after hearing the good news."

    Input: write an example for "学校" Output: "私は毎日学校に通います。"
`;

async function callOllama(prompt, options = {}) {
  try {
    const res = await fetch(LLM_OLLAMA_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gemma3:1b',
        prompt,
        stream: false,
        options,
      }),
    });
    if (!res.ok) {
      throw new Error(`Ollama returned status ${res.status}`);
    }
    const data = await res.json();
    return data.response;
  } catch (err) {
    console.warn(`Ollama call failed, falling back to Gemini. Error: ${err.message}`);
    return null;
  }
}

async function callGemini(prompt, systemInstruction = null) {
  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
  };
  if (systemInstruction) {
    payload.system_instruction = {
      parts: [{ text: systemInstruction }],
    };
  }

  const res = await fetch(LLM_GEMINI_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Gemini API returned status ${res.status}`);
  }
  const data = await res.json();
  try {
    return data.candidates[0].content.parts[0].text;
  } catch (e) {
    throw new Error(`Failed to parse Gemini response: ${JSON.stringify(data)}`);
  }
}

export async function genJoke() {
  const prompt = 'tell me a joke, add nothing else to the response, no emoji, max 240 chars';
  // Try local Ollama first
  const ollamaRes = await callOllama(prompt, { temperature: 0.8, top_p: 0.9 });
  if (ollamaRes) return ollamaRes;

  // Fallback to Gemini
  return await callGemini(prompt, 'You are a stand-up comedian. Tell a short joke under 240 characters. No emojis.');
}

export async function translateWord(word) {
  if (word.length > 30) {
    return `Word ${word} is too long`;
  }
  const prompt = `define ${word}, with IPA pronounce, short, max 240 chars, add 1 example. Format: word /IPA/ meaning\nexample:`;

  // Try local Ollama first
  const ollamaRes = await callOllama(prompt);
  if (ollamaRes) return ollamaRes;

  // Fallback to Gemini
  return await callGemini(prompt, 'You are a helpful dictionary bot.');
}

export async function translateSentence(s) {
  const prompt = `Translate this sentence to English '${s}', then break it down by chunks and explain words by words.`;
  return await callGemini(prompt, 'You are a Japanese-English teacher, you are concise, not adding unnecessary stuff in your answer.');
}

export async function genExample(wordDef) {
  if (!wordDef || wordDef.length > 100) {
    throw new Error('Input too long or invalid.');
  }
  const prompt = `write an example for "${wordDef}"`;
  return await callGemini(prompt, SYSTEM_PROMPT_GEN_EXAMPLE);
}

