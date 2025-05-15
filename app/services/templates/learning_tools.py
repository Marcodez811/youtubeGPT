TEMPLATE_FULL_QUIZ = """
You are an expert quiz maker. Given the transcript of a youtube video, generate a comprehensive quiz to test a university level student's understanding of the material.

Requirements:
- Generate 5 - 10 questions depending on the length and density of the transcript.
- Include a mix of question types: multiple choice, true/false, and short answer.
- Focus on the key facts, ideas, and reasoning conveyed in the transcript.
- Avoid overly specific details unless they are emphasized in the discussion.
- Use clear and concise language suitable for the target audience (university).

Transcript:
{transcript}

Format:
### Quiz:


1. **[Question 1]**
   a. Option A  
   b. Option B  
   c. Option C  
   d. Option D  

2. **[Question 2 - T/F]**  
   True or False 

3. **[Question 3 - Short Answer]**    

[...]

### Answer and explanation:

1. The answer to quiz 1 is **[answer 1]**, 
   because ...
2. The answer to quiz 2 is **[answer 2]**, 
   because ...
3. The answer to quiz 3 is **[answer 3]**, 
   because ...


[...]

Please ensure all questions are directly related to the content of the transcript and maintain a logical flow.
"""