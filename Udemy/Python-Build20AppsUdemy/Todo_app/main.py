user_prompt = "Enter a todo: "



while True:
    user_action = input("Type add, show, edit, complete  or exit:").strip().lower()
    match user_action:
        case "add":
            todo = input(user_prompt) + '\n'
            #file = open("todos.txt",'a')
            #file.writelines(todo)
            #file.close()
            with open('todos.txt','a') as file:
                todos = file.writelines(todo)

        case "show":
            with open('todos.txt','r') as file:
                todos = file.readlines()
                print(todos)
            for index,item in enumerate(todos):
                print(f"{index + 1}-{item}".strip('\n'))

        case "edit":
            number = int(input("which element you want to edit:"))
            number = number - 1
            new_todo = input("Enter new Todo:")

            with open('todos.txt','r') as file:
                todos = file.readlines()
                print(todos)
            todos[number] = new_todo  + "\n"
            print(todos)

            with open('todos.txt','w') as file:
                todos = file.writelines(todos)

        case "complete":
            number = int(input("Enter element number to remove (completed item)"))

            with open('todos.txt','r') as file:
                todos = file.readlines()

            index = number - 1
            todo_to_remove = todos[index].strip('\n')

            todos.pop(index)

            with open('todos.txt','w') as file:
                todos = file.writelines(todos)
                print(f"{todo_to_remove} was removed")

        case "exit":
            break
        case whatever:
            print("Enter a valid value")




