user_prompt = "Enter a todo: "



while True:
    user_action = input("Type add, show, edit  or exit:").strip().lower()
    match user_action:
        case "add":
            todo = input(user_prompt) + '\n'
            file = open("todos.txt",'a')
            file.writelines(todo)
            file.close()
        case "show":
            file = open("todos.txt",'r')
            todos = file.readlines()
            for index,item in enumerate(todos):
                print(f"{index + 1}-{item}".strip('\n'))
            file.close()
        case "edit":
            number = int(input("which element you want to edit:"))
            number = number - 1
            new_todo = input("Enter new Todo:")
            todos[number] = new_todo
        case "complete":
            number = int(input("Enter element number to remove (completed item)"))
            todos.pop(number-1)
            print("Item removed")
        case "exit":
            break
        case whatever:
            print("Enter a valid value")




