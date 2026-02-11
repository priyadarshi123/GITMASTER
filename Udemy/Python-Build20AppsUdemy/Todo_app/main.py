user_prompt = "Enter a todo: "

todos=[]

while True:
    user_action = input("Type add, show or exit:").strip().lower()
    match user_action:
        case "add":
            todo = input(user_prompt)
            todos.append(todo.capitalize())
        case "show":
            for todo in todos:
                print(todo.title())
        case "exit":
            break
        case whatever:
            print("Enter a valid value")




