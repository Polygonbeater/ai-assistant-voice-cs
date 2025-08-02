from llama_cpp import Llama

MODEL_PATH = "./models/csmpt7b.Q8_0.gguf"

llm = Llama(model_path=MODEL_PATH)

def generate(prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> str:
    response = llm(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=None,
        echo=False,
    )
    return response['choices'][0]['text']

if __name__ == "__main__":
    test_prompt = "Ahoj, jak se máš?"
    print(generate(test_prompt))
