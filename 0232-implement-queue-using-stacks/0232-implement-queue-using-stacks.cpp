class MyQueue {
public:
    stack<int> s1;
    stack<int> s2;

    MyQueue() {
    }

    void push(int x) {
        s1.push(x);
    }

    int pop() {
        move();

        int ans = s2.top();
        s2.pop();

        return ans;
    }

    int peek() {
        move();

        return s2.top();
    }

    bool empty() {
        return s1.empty() && s2.empty();
    }

private:
    void move() {
        if (s2.empty()) {
            while (!s1.empty()) {
                s2.push(s1.top());
                s1.pop();
            }
        }
    }
};